from datetime import date, timedelta
from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_submit_valid_aoi():
    """
    Test submitting a valid GeoJSON polygon with proper date bounds.
    """
    payload = {
        "name": "Test Parcel 1",
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-62.20, -3.40],
                    [-62.18, -3.40],
                    [-62.18, -3.42],
                    [-62.20, -3.42],
                    [-62.20, -3.40]  # Closed polygon loop
                ]
            ]
        }
    }
    
    response = client.post("/api/aoi", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert "aoi_id" in data


def test_submit_invalid_unclosed_polygon():
    """
    Test submitting a polygon whose coordinates do not form a closed loop.
    """
    payload = {
        "name": "Test Unclosed",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)),
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-62.2, -3.4],
                    [-62.1, -3.4],
                    [-62.1, -3.5],
                    [-62.2, -3.5]  # Missing closed point
                ]
            ]
        }
    }
    
    response = client.post("/api/aoi", json=payload)
    # Fastapi/Shapely will catch the malformed polygon or unclosed shape
    assert response.status_code in [400, 422]


def test_submit_invalid_date_timeline():
    """
    Test submitting when start_date is after end_date.
    """
    payload = {
        "name": "Test Dates",
        "start_date": str(date.today() + timedelta(days=30)),
        "end_date": str(date.today()),
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-62.20, -3.40],
                    [-62.18, -3.40],
                    [-62.18, -3.42],
                    [-62.20, -3.42],
                    [-62.20, -3.40]
                ]
            ]
        }
    }
    
    response = client.post("/api/aoi", json=payload)
    assert response.status_code == 400
    assert "Invalid monitoring timeline" in response.json()["detail"]


def test_submit_area_too_large():
    """
    Test submitting a polygon that exceeds the 5000 ha area cap.
    """
    payload = {
        "name": "Massive Parcel",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)),
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-62.0, -3.0],
                    [-61.0, -3.0],
                    [-61.0, -4.0],
                    [-62.0, -4.0],
                    [-62.0, -3.0]  # Very large bounding polygon
                ]
            ]
        }
    }
    
    response = client.post("/api/aoi", json=payload)
    assert response.status_code == 400
    assert "Area exceeds maximum" in response.json()["detail"]
