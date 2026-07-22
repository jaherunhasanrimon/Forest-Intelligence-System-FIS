import io
import os
import time
import zipfile
import logging
import requests
import ee
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models.job import Job
from app.models.aoi import AOI
from app.models.satellite_dataset import SatelliteDataset
from app.services.gee_service import authenticate_gee
from app.services.gee_script import create_10band_composite
from app.services.job_orchestrator import update_job_status
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def download_gee_image_locally(image: ee.Image, aoi_geom: ee.Geometry, job_id: int) -> str:
    """
    Download GeoTIFF image directly from GEE via HTTP stream download URL.
    Saves to local_storage_path without requiring Google Cloud Storage billing.
    """
    output_dir = os.path.join(settings.LOCAL_STORAGE_PATH, "geotiffs")
    os.makedirs(output_dir, exist_ok=True)
    target_tif_path = os.path.join(output_dir, f"job_{job_id}.tif")

    logger.info("Generating GEE direct download URL for Job ID %d...", job_id)
    download_url = image.getDownloadURL({
        "name": f"job_{job_id}",
        "scale": 10,  # 10m spatial resolution
        "crs": "EPSG:4326",
        "region": aoi_geom,
        "format": "GEO_TIFF",
        "filePerBand": False
    })

    logger.info("Downloading satellite composite GeoTIFF stream for Job ID %d...", job_id)
    resp = requests.get(download_url, timeout=120)
    resp.raise_for_status()

    # Check if GEE returned a zip file or direct tif bytes
    content = resp.content
    if content.startswith(b"PK\x03\x04"):
        # Extract the .tif file from the downloaded zip buffer
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
    logger.info("Successfully downloaded GeoTIFF to %s (%.2f MB)", target_tif_path, file_size / (1024 * 1024))
    return target_tif_path


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
        else:
            local_path = download_gee_image_locally(composite_image, aoi_geom, job_id)
            gcs_uri = None

        # 6. Save SatelliteDataset record in DB
        file_size_mb = os.path.getsize(local_path) / (1024 * 1024) if local_path and os.path.exists(local_path) else 0.0
        
        dataset = db.query(SatelliteDataset).filter(SatelliteDataset.job_id == job_id).first()
        if not dataset:
            dataset = SatelliteDataset(
                job_id=job_id,
                gcs_uri=gcs_uri,
                local_path=local_path,
                band_count=metadata.get("band_count", 10),
                resolution_m=10.0,
                crs="EPSG:4326",
                file_size_mb=round(file_size_mb, 2)
            )
            db.add(dataset)
        else:
            dataset.gcs_uri = gcs_uri
            dataset.local_path = local_path
            dataset.file_size_mb = round(file_size_mb, 2)

        db.commit()

        # 7. Update status to EXPORTED
        update_job_status(db, job_id, "EXPORTED")
        logger.info("GEE Export task for Job ID %d complete.", job_id)

    except Exception as exc:
        logger.exception("GEE Export Task failed for Job ID %d:", job_id)
        update_job_status(db, job_id, "FAILED", error_message=str(exc))
        raise exc
    finally:
        db.close()
