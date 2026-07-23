import io
import os
import time
import zipfile
import logging
from typing import Dict, Any, Optional, Tuple
import requests
import ee
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.job import Job
from app.models.aoi import AOI
from app.models.satellite_dataset import SatelliteDataset
from app.services.drive_service import upload_geotiff_to_drive, get_drive_file_web_url
from app.services.gee_service import authenticate_gee
from app.services.gee_script import create_10band_composite
from app.services.job_orchestrator import update_job_status
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def download_gee_image_locally(image: ee.Image, aoi_geom: ee.Geometry, job_id: int) -> str:
    """
    Download GeoTIFF image directly from GEE via HTTP stream download URL.
    Saves to local_storage_path without requiring Google Cloud Storage billing.
    Uses adaptive scale fallback (10m -> 20m -> 30m -> 60m) to stay under GEE's 50MB direct download payload limit.
    """
    output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "geotiffs")
    os.makedirs(output_dir, exist_ok=True)
    target_tif_path = os.path.join(output_dir, f"job_{job_id}.tif")

    scales_to_try = [10, 20, 30, 60]
    last_error = None

    for scale in scales_to_try:
        try:
            logger.info("Attempting GEE direct download for Job ID %d at %dm resolution...", job_id, scale)
            download_url = image.getDownloadURL({
                "name": f"job_{job_id}",
                "scale": scale,
                "crs": "EPSG:4326",
                "region": aoi_geom,
                "format": "GEO_TIFF",
                "filePerBand": False
            })

            logger.info("Downloading satellite composite GeoTIFF stream for Job ID %d (scale=%dm)...", job_id, scale)
            resp = requests.get(download_url, timeout=120)

            if not resp.ok:
                error_text = resp.text
                if "must be less than or equal to 50331648 bytes" in error_text or resp.status_code == 400:
                    logger.warning("GEE payload limit (50MB) exceeded for Job #%d at %dm scale. Retrying with coarser scale...", job_id, scale)
                    last_error = f"GEE payload limit (50MB) exceeded at {scale}m scale."
                    continue
                resp.raise_for_status()

            content = resp.content
            if content.startswith(b"PK\x03\x04"):
                with zipfile.ZipFile(io.BytesIO(content)) as zip_ref:
                    tif_files = [f for f in zip_ref.namelist() if f.endswith(".tif")]
                    if not tif_files:
                        raise RuntimeError("GEE Zip archive did not contain any .tif files.")
                    extracted_bytes = zip_ref.read(tif_files[0])
                    with open(target_tif_path, "wb") as f:
                        f.write(extracted_bytes)
            else:
                with open(target_tif_path, "wb") as f:
                    f.write(content)

            file_size = os.path.getsize(target_tif_path)
            logger.info("Successfully downloaded GeoTIFF (%dm resolution) to %s (%.2f MB)", scale, target_tif_path, file_size / (1024 * 1024))
            return target_tif_path

        except Exception as exc:
            last_error = str(exc)
            logger.warning("Download failed at %dm scale: %s. Trying next scale...", scale, exc)

    raise RuntimeError(f"GEE Direct Download failed for Job #{job_id}. {last_error}")


def export_gee_image_to_drive(image: ee.Image, aoi_geom: ee.Geometry, job_id: int) -> tuple[Optional[str], Optional[str]]:
    """
    Download GeoTIFF from GEE directly (adaptive scale), then upload to Google Drive.
    """
    local_path = download_gee_image_locally(image, aoi_geom, job_id)

    remote_filename = f"job_{job_id}.tif"
    folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
    drive_file_id = upload_geotiff_to_drive(local_path, remote_filename, folder_id)
    drive_web_url = get_drive_file_web_url(drive_file_id) if drive_file_id else None

    logger.info(
        "GeoTIFF for Job #%d processed for Drive export — file ID: %s, URL: %s",
        job_id, drive_file_id, drive_web_url
    )
    return drive_file_id, drive_web_url


def export_gee_image_to_gcs(image: ee.Image, aoi_geom: ee.Geometry, job_id: int) -> str:
    """
    Initiate GEE batch Export task to Google Cloud Storage bucket.
    """
    remote_key = f"geotiffs/job_{job_id}"
    logger.info("Submitting GEE Cloud Storage Export Task to gs://%s/%s.tif...", settings.GCS_BUCKET_NAME, remote_key)
    
    task = ee.batch.Export.image.toCloudStorage(
        image=image,
        description=f"FIS_Job_{job_id}_Export",
        bucket=settings.GCS_BUCKET_NAME,
        fileNamePrefix=remote_key,
        scale=10,
        region=aoi_geom,
        fileFormat="GeoTIFF",
        maxPixels=1e9
    )
    task.start()

    # Poll GEE Batch task status
    logger.info("GEE Batch Task %s started. Polling task status...", task.id)
    while True:
        status_info = task.status()
        state = status_info.get("state")
        if state == "COMPLETED":
            logger.info("GEE Export task %s completed successfully.", task.id)
            break
        elif state in ["FAILED", "CANCELLED"]:
            error_msg = status_info.get("error_message", "Unknown GEE export error")
            raise RuntimeError(f"GEE Batch Export Task failed with state '{state}': {error_msg}")
        
        time.sleep(5)

    return f"gs://{settings.GCS_BUCKET_NAME}/{remote_key}.tif"


@celery_app.task(name="app.tasks.gee_export_tasks.run_gee_export_task")
def run_gee_export_task(job_id: int):
    """
    Celery task: Authenticate GEE, generate 10-band composite, and export image.
    """
    logger.info("Starting GEE Export Task for Job ID: %d", job_id)
    db = SessionLocal()
    try:
        # 1. Update job status to EXPORTING
        update_job_status(db, job_id, "EXPORTING")

        # 2. Fetch Job and AOI records from DB
        db_job = db.query(Job).filter(Job.id == job_id).first()
        if not db_job:
            raise ValueError(f"Job #{job_id} not found in database.")

        db_aoi = db.query(AOI).filter(AOI.id == db_job.aoi_id).first()
        if not db_aoi:
            raise ValueError(f"AOI #{db_job.aoi_id} associated with Job #{job_id} not found.")

        # 3. Authenticate with GEE
        authenticate_gee()

        # 4. Generate 10-band composite
        start_str = db_job.start_date.strftime("%Y-%m-%d")
        end_str = db_job.end_date.strftime("%Y-%m-%d")
        composite_image, metadata = create_10band_composite(db_aoi.geometry, start_str, end_str)

        aoi_geom = ee.Geometry(db_aoi.geometry)

        # 5. Export according to configured storage backend
        backend = settings.effective_storage_backend
        if backend == "gcs":
            gcs_uri = export_gee_image_to_gcs(composite_image, aoi_geom, job_id)
            local_path = None
            drive_file_id = None
            drive_web_url = None
        elif backend == "drive":
            # export_gee_image_to_drive internally calls download_gee_image_locally first
            # so the file is also present at storage/geotiffs/job_{id}.tif locally
            drive_file_id, drive_web_url = export_gee_image_to_drive(composite_image, aoi_geom, job_id)
            local_path = os.path.join(settings.LOCAL_STORAGE_PATH, "geotiffs", f"job_{job_id}.tif")
            gcs_uri = None
        else:
            local_path = download_gee_image_locally(composite_image, aoi_geom, job_id)
            gcs_uri = None
            drive_file_id = None
            drive_web_url = None

        # 6. Save SatelliteDataset record in DB
        file_size_mb = os.path.getsize(local_path) / (1024 * 1024) if local_path and os.path.exists(local_path) else 0.0

        dataset = db.query(SatelliteDataset).filter(SatelliteDataset.job_id == job_id).first()
        if not dataset:
            dataset = SatelliteDataset(
                job_id=job_id,
                gcs_uri=gcs_uri,
                local_path=local_path,
                drive_file_id=drive_file_id,
                drive_web_url=drive_web_url,
                band_count=metadata.get("band_count", 10),
                resolution_m=10.0,
                crs="EPSG:4326",
                file_size_mb=round(file_size_mb, 2)
            )
            db.add(dataset)
        else:
            dataset.gcs_uri = gcs_uri
            dataset.local_path = local_path
            dataset.drive_file_id = drive_file_id
            dataset.drive_web_url = drive_web_url
            dataset.file_size_mb = round(file_size_mb, 2)

        db.commit()

        # 7. Update status to EXPORTED
        update_job_status(db, job_id, "EXPORTED")
        logger.info("GEE Export task for Job ID %d complete.", job_id)

    except Exception as exc:
        logger.exception("GEE Export Task failed for Job ID %d:", job_id)
        err_msg = str(exc)
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            try:
                err_json = exc.response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg = err_json["error"]["message"]
            except Exception:
                err_msg = f"{exc} ({exc.response.text[:150]})"

        update_job_status(db, job_id, "FAILED", error_message=err_msg)
        raise exc
    finally:
        db.close()
