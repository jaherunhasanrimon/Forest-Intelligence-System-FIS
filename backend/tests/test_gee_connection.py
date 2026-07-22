from app.services.gee_service import verify_gee_connection


def test_gee_connection():
    """
    Smoke test to check Earth Engine authentication and connection.
    This runs against the live Earth Engine servers using the configured credentials.
    """
    # Attempt to verify the connection
    result = verify_gee_connection()
    
    # Assert that connection is verified
    assert result is True, "Google Earth Engine connection verification failed. Make sure secrets are correctly configured."
