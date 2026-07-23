import os
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    # App Settings
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "temporary_secret_key_for_dev_change_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # MySQL Settings
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "forest_intel"
    MYSQL_USER: str = "fis_user"
    MYSQL_PASSWORD: str = "fis_password"

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Google Earth Engine Settings
    GEE_SERVICE_ACCOUNT_EMAIL: str
    GEE_SERVICE_ACCOUNT_KEY_PATH: str = "backend/secrets/gee-service-account.json"

    # -------------------------------------------------------------------------
    # Storage / Export Backend
    # -------------------------------------------------------------------------
    # STORAGE_BACKEND controls which provider is used for GeoTIFF storage:
    #   "local"  — saves files to LOCAL_STORAGE_PATH on disk.
    #              No cloud credentials required. Default for development.
    #   "gcs"    — Google Cloud Storage. Requires GCS_BUCKET_NAME and billing.
    #   "drive"  — Google Drive. Uploads GeoTIFFs to the shared Drive folder.
    #              Requires GOOGLE_DRIVE_FOLDER_ID and Drive API enabled.
    #
    # To switch backends, just change STORAGE_BACKEND in .env.
    # -------------------------------------------------------------------------
    STORAGE_BACKEND: str = "local"

    # GCS bucket name. Set to "not-configured" when GCS is unavailable.
    GCS_BUCKET_NAME: str = "not-configured"

    # Google Drive folder ID for GeoTIFF exports.
    # Share the target Drive folder with the service account email as Editor.
    # Set to "not-configured" when Drive backend is not in use.
    GOOGLE_DRIVE_FOLDER_ID: str = "not-configured"

    # Root directory for local file storage (geotiffs, outputs, reports)
    LOCAL_STORAGE_PATH: str = "storage"

    # Google Maps API Key
    GOOGLE_MAPS_API_KEY: str = ""

    # Pydantic Settings Config
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    USE_MYSQL: bool = True
    DATABASE_URL_OVERRIDE: str = ""

    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        if self.USE_MYSQL:
            return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        return "sqlite:///./dev.db"

    @property
    def resolved_key_path(self) -> str:
        """
        Returns the GEE service account key path as an absolute path.

        The value in .env may be relative (e.g. "backend/secrets/gee-service-account.json").
        This property tries, in order:
          1. The path as-is (works if the CWD is the project root).
          2. Relative to backend/ (works if the CWD is inside backend/).
          3. Relative to the parent of backend/ (project root anchor).
        The first existing path wins; if none exist, the raw value is returned
        so the caller gets a clear FileNotFoundError with the attempted path.
        """
        raw = self.GEE_SERVICE_ACCOUNT_KEY_PATH
        candidates = [
            raw,                                                   # as-is
            os.path.join(BACKEND_DIR, raw),                 # relative to backend/
            os.path.join(os.path.dirname(BACKEND_DIR), raw), # relative to project root
        ]
        for path in candidates:
            if os.path.exists(path):
                return os.path.abspath(path)
        return raw  # return raw so the caller's FileNotFoundError is descriptive

    @property
    def gcs_configured(self) -> bool:
        """True only when a real GCS bucket name has been provided."""
        return self.GCS_BUCKET_NAME not in ("", "not-configured")

    @property
    def drive_configured(self) -> bool:
        """True only when a Google Drive folder ID has been provided."""
        return self.GOOGLE_DRIVE_FOLDER_ID not in ("", "not-configured")

    @property
    def effective_storage_backend(self) -> str:
        """
        Returns the storage backend that will actually be used.

        Falls back to 'local' if the configured backend is not fully set up:
          - 'gcs' without GCS_BUCKET_NAME  → 'local'
          - 'drive' without GOOGLE_DRIVE_FOLDER_ID → 'local'
        """
        if self.STORAGE_BACKEND == "gcs" and not self.gcs_configured:
            return "local"
        if self.STORAGE_BACKEND == "drive" and not self.drive_configured:
            return "local"
        return self.STORAGE_BACKEND


settings = Settings()
