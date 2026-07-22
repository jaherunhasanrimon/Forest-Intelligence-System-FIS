"""
Phase 0 Verification Script — Google Earth Engine Connection
============================================================

Purpose:
    Verify that the GEE service account credentials are valid and that
    the Earth Engine API is reachable from this codebase.
    Also reports the active storage backend without requiring GCS.

Exit criterion for Phase 0:
    This script exits with code 0 and prints the GEE verification success
    message.  GCS does NOT need to be configured for Phase 0 to pass.

Usage (run from the project root, NOT from inside backend/):
    python backend/scripts/verify_gee.py

Prerequisites:
    1. backend/.env configured with GEE_SERVICE_ACCOUNT_EMAIL
    2. GEE service account JSON at GEE_SERVICE_ACCOUNT_KEY_PATH
    3. pip install -r backend/requirements.txt
"""

import os
import sys

# ---------------------------------------------------------------------------
# Ensure `app` package is importable regardless of where the script is run from
# ---------------------------------------------------------------------------
# Supports running from the project root:   python backend/scripts/verify_gee.py
# And from inside the backend/ directory:   python scripts/verify_gee.py
_script_dir   = os.path.dirname(os.path.abspath(__file__))          # .../backend/scripts/
_backend_dir  = os.path.dirname(_script_dir)                        # .../backend/
_project_root = os.path.dirname(_backend_dir)                       # .../Forest-Intelligence-System-FIS/

if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Load .env from backend/ before importing anything that reads settings
from dotenv import load_dotenv   # noqa: E402 (import after sys.path setup)
load_dotenv(os.path.join(_backend_dir, ".env"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "=", width: int = 60) -> str:
    return char * width


def _ok(msg: str) -> str:
    return f"  ✅  {msg}"


def _warn(msg: str) -> str:
    return f"  ⚠️   {msg}"


def _fail(msg: str) -> str:
    return f"  ❌  {msg}"


# ---------------------------------------------------------------------------
# Main verification steps
# ---------------------------------------------------------------------------

def step_config() -> bool:
    """Step 1: Load and validate configuration."""
    print("\n[1/3] Checking configuration ...")

    from app.config import settings  # noqa: PLC0415

    email    = settings.GEE_SERVICE_ACCOUNT_EMAIL
    key_path = settings.resolved_key_path

    print(f"      GEE account  : {email or '(not set)'}")
    print(f"      Key file     : {key_path}")

    if not email:
        print(_fail("GEE_SERVICE_ACCOUNT_EMAIL is not set in .env"))
        return False

    if not os.path.exists(key_path):
        print(_fail(f"Service-account key not found: {key_path}"))
        print("       → Place your GEE JSON key at that path and try again.")
        return False

    # Report storage backend — GCS not required for Phase 0
    backend_configured = settings.effective_storage_backend
    if settings.gcs_configured:
        print(f"      Storage      : GCS  (bucket: {settings.GCS_BUCKET_NAME})")
    else:
        print(f"      Storage      : {backend_configured}  (GCS not configured — OK for development)")

    print(_ok("Configuration OK"))
    return True


def step_authenticate() -> bool:
    """Step 2: Authenticate with Earth Engine."""
    print("\n[2/3] Authenticating with Google Earth Engine ...")

    from app.services.gee_service import authenticate_gee  # noqa: PLC0415

    try:
        authenticate_gee()
        print(_ok("Authentication successful"))
        return True
    except Exception as exc:
        print(_fail(f"Authentication failed: {exc}"))
        return False


def step_verify_api() -> bool:
    """Step 3: Run a trivial server-side computation to confirm the API is live."""
    import time  # noqa: PLC0415
    print("\n[3/3] Running test Earth Engine computation (1 + 1) ...")

    from app.services.gee_service import verify_gee_connection  # noqa: PLC0415

    try:
        start  = time.monotonic()
        passed = verify_gee_connection()
        elapsed = time.monotonic() - start

        if passed:
            print(f"      Result: 2  ✓   ({elapsed:.2f}s round-trip)")
            print(_ok("API call successful — GEE connection verified: 2"))
            return True
        else:
            print(_fail("API returned unexpected result (expected 2)"))
            return False
    except Exception as exc:
        print(_fail(f"API call raised an exception: {exc}"))
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(_hr())
    print("  Forest Intelligence System — Phase 0 Verification")
    print(_hr())

    steps = [step_config, step_authenticate, step_verify_api]

    for step_fn in steps:
        if not step_fn():
            print()
            print(_hr("-"))
            print(_fail("Phase 0 verification FAILED.  Fix the error above and re-run."))
            print(_hr("-"))
            sys.exit(1)

    print()
    print(_hr())
    print("  ✅  PHASE 0 EXIT CRITERION MET")
    print("  GEE call succeeded end-to-end from the new codebase.")
    print("  GCS is optional — storage backend falls back to local.")
    print(_hr())
    sys.exit(0)


if __name__ == "__main__":
    main()
