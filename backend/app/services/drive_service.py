"""
Google Drive Service
====================

Handles uploading and downloading GeoTIFF satellite composite files
to/from a shared Google Drive folder using the GEE service account credentials.

The service account must be granted Editor access to the target Drive folder.
Folder ID is read from GOOGLE_DRIVE_FOLDER_ID in .env.

Public API
----------
- ``get_drive_service()``             → Authenticated Drive API client.
- ``upload_geotiff_to_drive()``       → Upload a local .tif to Drive; returns file ID.
- ``download_geotiff_from_drive()``   → Download a file from Drive to a local path.
- ``get_drive_file_web_url()``        → Returns the Drive web view URL for a file ID.
"""

import io
import logging
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from app.config import settings

logger = logging.getLogger(__name__)

# Drive API scopes needed — file-level read/write in the shared folder
_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def get_drive_service():
    """
    Build and return an authenticated Google Drive API v3 service client.
    Uses the same service account JSON key as GEE authentication.
    """
    key_path = settings.resolved_key_path
    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=_DRIVE_SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    logger.info("Google Drive API service authenticated with service account: %s", settings.GEE_SERVICE_ACCOUNT_EMAIL)
    return service


def upload_geotiff_to_drive(local_tif_path: str, remote_filename: str, folder_id: str) -> str:
    """
    Upload a local GeoTIFF file to a Google Drive folder.

    Args:
        local_tif_path: Absolute or relative path to the local .tif file.
        remote_filename: The file name to use in Google Drive (e.g. 'job_17.tif').
        folder_id: Google Drive folder ID to upload into.

    Returns:
        Google Drive file ID (str) of the newly uploaded file.
    """
    service = get_drive_service()

    file_metadata = {
        "name": remote_filename,
        "parents": [folder_id],
        "mimeType": "image/tiff"
    }
    media = MediaFileUpload(local_tif_path, mimetype="image/tiff", resumable=False)

    logger.info("Uploading GeoTIFF '%s' to Drive folder '%s'...", remote_filename, folder_id)
    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, size, webViewLink",
            supportsAllDrives=True
        ).execute()

        file_id = file.get("id")
        file_size = file.get("size", "?")
        logger.info(
            "Drive upload complete — file: %s, ID: %s, size: %s bytes",
            remote_filename, file_id, file_size
        )
        return file_id
    except Exception as exc:
        err_str = str(exc)
        if "storageQuotaExceeded" in err_str or "Service Accounts do not have storage quota" in err_str or "403" in err_str:
            logger.warning(
                "Google Drive API quota restriction encountered for Service Account (%s). "
                "The GeoTIFF will be stored and processed via GEE Direct Stream fallback.",
                exc
            )
            return None
        raise exc


def download_geotiff_from_drive(file_id: str, dest_path: str) -> str:
    """
    Download a GeoTIFF file from Google Drive to a local path.

    Args:
        file_id: Google Drive file ID to download.
        dest_path: Local destination path to write the file to.

    Returns:
        dest_path (str) after successful download.
    """
    service = get_drive_service()

    logger.info("Downloading Drive file '%s' to local path '%s'...", file_id, dest_path)
    request = service.files().get_media(fileId=file_id)

    with io.FileIO(dest_path, mode="wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.debug("Drive download progress: %.1f%%", status.progress() * 100)

    logger.info("Drive download complete — saved to: %s", dest_path)
    return dest_path


def get_drive_file_web_url(file_id: str) -> str:
    """
    Return the Google Drive web view URL for a given file ID.
    """
    return f"https://drive.google.com/file/d/{file_id}/view"


def delete_file_from_drive(file_id: str) -> None:
    """
    Delete a file from Google Drive by file ID.
    """
    try:
        service = get_drive_service()
        logger.info("Deleting file '%s' from Google Drive...", file_id)
        service.files().delete(fileId=file_id).execute()
        logger.info("File '%s' successfully deleted from Google Drive.", file_id)
    except Exception as exc:
        logger.warning("Failed to delete file '%s' from Google Drive: %s", file_id, exc)

