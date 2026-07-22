"""
Storage Service — Abstract Export Provider
==========================================

Why this abstraction exists
----------------------------
GEE exports a GeoTIFF to a cloud destination (GCS or Drive), then we need to
download it, store it locally for the AI pipeline, and later serve it.
The *destination* varies by environment:

  Development  →  local disk (no billing needed)
  Staging/Prod →  Google Cloud Storage  (same service account as GEE)
  Alternative  →  Google Drive          (future, for orgs without GCS billing)

All Celery tasks call ``get_storage_provider()`` — they never reference GCS,
Drive, or local disk directly.  Switching backends is a one-line .env change:

  STORAGE_BACKEND=local    (default; works without any cloud account)
  STORAGE_BACKEND=gcs      (requires GCS_BUCKET_NAME + billing)
  STORAGE_BACKEND=drive    (not yet implemented; stub raises NotImplementedError)

How to add a new backend
------------------------
1. Create a class that inherits ``StorageProvider`` and implements all three
   abstract methods (``upload``, ``download``, ``exists``).
2. Register it in ``get_storage_provider()`` with a new string key.
3. That's it — no task code changes needed.
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.config import settings


# ---------------------------------------------------------------------------
# Abstract Interface
# ---------------------------------------------------------------------------

class StorageProvider(ABC):
    """
    Common interface for all storage backends.

    All methods deal in *remote_key* — a relative identifier for the file
    within the backend (e.g. ``"geotiffs/job_42.tif"``).  What that key
    maps to physically depends on the backend:
      - LocalStorageProvider  →  ``storage/geotiffs/job_42.tif``
      - GCSStorageProvider    →  ``gs://bucket/geotiffs/job_42.tif``
      - DriveStorageProvider  →  a Drive file ID (future)
    """

    @abstractmethod
    def upload(self, local_path: str, remote_key: str) -> str:
        """
        Copy a local file into the storage backend.

        Args:
            local_path:  Absolute path to the file on this machine.
            remote_key:  Relative key/name for the file in the backend.

        Returns:
            A URI or path string that uniquely identifies the stored file.
        """

    @abstractmethod
    def download(self, remote_key: str, local_path: str) -> Path:
        """
        Retrieve a file from the storage backend to a local path.

        Args:
            remote_key:  Key used when the file was uploaded.
            local_path:  Destination on this machine (parent dirs created).

        Returns:
            Path object pointing to the downloaded file.
        """

    @abstractmethod
    def exists(self, remote_key: str) -> bool:
        """Return True if the file exists in the backend."""

    def backend_name(self) -> str:
        """Human-readable name used in logs and health checks."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# Backend: Local Disk
# ---------------------------------------------------------------------------

class LocalStorageProvider(StorageProvider):
    """
    Saves files under a local directory tree.  No cloud account required.

    This is the default for development and works identically to the cloud
    providers from the task layer's point of view — the same interface,
    just using shutil instead of a GCS/Drive client.

    Files live at:  {LOCAL_STORAGE_PATH}/{remote_key}
    e.g.            storage/geotiffs/job_42.tif
    """

    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = Path(base_path or settings.LOCAL_STORAGE_PATH)

    def _resolve(self, remote_key: str) -> Path:
        """Resolve a remote key to an absolute local path."""
        return self.base_path / remote_key

    def upload(self, local_path: str, remote_key: str) -> str:
        destination = self._resolve(remote_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, destination)
        return str(destination)

    def download(self, remote_key: str, local_path: str) -> Path:
        source = self._resolve(remote_key)
        if not source.exists():
            raise FileNotFoundError(f"[LocalStorage] File not found: {source}")
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def exists(self, remote_key: str) -> bool:
        return self._resolve(remote_key).exists()

    def backend_name(self) -> str:
        return f"local:{self.base_path}"


# ---------------------------------------------------------------------------
# Backend: Google Cloud Storage
# ---------------------------------------------------------------------------

class GCSStorageProvider(StorageProvider):
    """
    Stores files in a GCS bucket.

    Requires:
      - GCS_BUCKET_NAME set to a real bucket name (not 'not-configured')
      - The GEE service account must have Storage Object Admin on the bucket
        (the same service account key already used for Earth Engine works).
      - google-cloud-storage installed (already in requirements.txt)

    This provider shares service account credentials with the GEE provider,
    so no extra OAuth consent or separate key file is needed.
    """

    def __init__(self) -> None:
        if not settings.gcs_configured:
            raise RuntimeError(
                "GCSStorageProvider requires GCS_BUCKET_NAME to be set.\n"
                "Either configure a bucket or set STORAGE_BACKEND=local in .env."
            )
        # Lazy import — google-cloud-storage is installed but we don't want
        # the import at module load time when the provider isn't selected.
        from google.cloud import storage as gcs
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            settings.GEE_SERVICE_ACCOUNT_KEY_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self._client = gcs.Client(credentials=credentials)
        self._bucket = self._client.bucket(settings.GCS_BUCKET_NAME)

    def upload(self, local_path: str, remote_key: str) -> str:
        blob = self._bucket.blob(remote_key)
        blob.upload_from_filename(local_path)
        return f"gs://{settings.GCS_BUCKET_NAME}/{remote_key}"

    def download(self, remote_key: str, local_path: str) -> Path:
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        blob = self._bucket.blob(remote_key)
        blob.download_to_filename(str(destination))
        return destination

    def exists(self, remote_key: str) -> bool:
        return self._bucket.blob(remote_key).exists()

    def backend_name(self) -> str:
        return f"gcs:{settings.GCS_BUCKET_NAME}"


# ---------------------------------------------------------------------------
# Backend: Google Drive  (stub — Phase 4 future option)
# ---------------------------------------------------------------------------

class DriveStorageProvider(StorageProvider):
    """
    Google Drive storage provider.

    Not yet implemented.  Drive is usable without billing, but requires a
    different authentication flow (Drive API scope) and lacks features that
    GCS provides (object listing, lifecycle rules, byte-range reads).

    To implement:
      1. Add google-api-python-client to requirements.txt
      2. Build a Drive API client using the service account credentials
      3. Implement upload/download/exists using the Files resource
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "DriveStorageProvider is not yet implemented.\n"
            "Use STORAGE_BACKEND=local for development or STORAGE_BACKEND=gcs for production."
        )

    def upload(self, local_path: str, remote_key: str) -> str:
        raise NotImplementedError

    def download(self, remote_key: str, local_path: str) -> Path:
        raise NotImplementedError

    def exists(self, remote_key: str) -> bool:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Factory — the only function tasks should call
# ---------------------------------------------------------------------------

def get_storage_provider() -> StorageProvider:
    """
    Return the configured storage provider instance.

    Called by every Celery task that reads or writes files.
    Never instantiate a provider directly in task code.

    Selection order:
      1. Read STORAGE_BACKEND from settings.
      2. If STORAGE_BACKEND=gcs but GCS is not configured, fall back to local
         (settings.effective_storage_backend handles this automatically).
      3. Raise ValueError for unrecognized backend names.
    """
    backend = settings.effective_storage_backend

    if backend == "local":
        return LocalStorageProvider()
    elif backend == "gcs":
        return GCSStorageProvider()
    elif backend == "drive":
        return DriveStorageProvider()
    else:
        raise ValueError(
            f"Unknown STORAGE_BACKEND: '{backend}'. "
            "Valid values: 'local', 'gcs', 'drive'."
        )
