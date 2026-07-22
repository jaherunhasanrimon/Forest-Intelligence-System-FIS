"""
Google Earth Engine Authentication Service
==========================================

Why a service account — not personal OAuth
-------------------------------------------
Personal OAuth pops up a browser consent screen each time it expires.
A service account authenticates silently using a JSON key file, which is
what makes the pipeline truly automatic (no human in the loop).

The service account email + key path are read from environment variables
via ``app.config.settings`` — never hardcoded in source code.

Public API
----------
- ``authenticate_gee()``   → Call once before any ``ee.*`` operation.
- ``verify_gee_connection()`` → Smoke-test that auth + API round-trip works.
"""

import logging

import ee

from app.config import settings

logger = logging.getLogger(__name__)


def authenticate_gee() -> None:
    """
    Authenticate with Google Earth Engine using a service account.

    Reads credentials from:
      - GEE_SERVICE_ACCOUNT_EMAIL (env var)
      - GEE_SERVICE_ACCOUNT_KEY_PATH (env var, resolved to absolute path)

    Raises:
        ValueError:         If GEE_SERVICE_ACCOUNT_EMAIL is empty.
        FileNotFoundError:  If the key file cannot be found at any candidate path.
        ee.EEException:     If GEE rejects the credentials.
    """
    email    = settings.GEE_SERVICE_ACCOUNT_EMAIL
    key_path = settings.resolved_key_path  # absolute path, path-searched

    if not email:
        raise ValueError(
            "GEE_SERVICE_ACCOUNT_EMAIL is not set. "
            "Add it to backend/.env and restart."
        )

    logger.info("Authenticating with GEE — service account: %s", email)

    credentials = ee.ServiceAccountCredentials(email=email, key_file=key_path)
    ee.Initialize(credentials)

    logger.info("GEE authentication successful.")


def verify_gee_connection() -> bool:
    """
    Confirm that authentication works and the GEE API is reachable.

    Runs a trivial server-side computation (1 + 1 = 2) — no imagery loaded,
    no quota consumed beyond a minimal API call.

    Returns:
        True if the API returns the expected result (2), False otherwise.
    """
    authenticate_gee()

    result = ee.Number(1).add(1).getInfo()
    success = result == 2

    if success:
        logger.info("GEE connection verified. Server returned: %s", result)
    else:
        logger.error("GEE connection test failed. Expected 2, got: %s", result)

    return success
