import os
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_end_to_end_report_generation_and_download():
    """
    Integration test: Submitting an AOI runs GEE export -> AI Analysis -> Report Generation.
    Validates that PDF and HTML report files are created on disk and available via download API.
    """
    payload = {
        "name": "Executive Report Test Parcel",
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
                    [-62.20, -3.40]
                ]
            ]
        }
    }

    # 1. Submit AOI
    submit_resp = client.post("/api/aoi", json=payload)
    assert submit_resp.status_code == 202
    job_id = submit_resp.json()["job_id"]

    # 2. Check Job status completed
    status_resp = client.get(f"/api/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"

    # 3. Test PDF Download endpoint
    pdf_resp = client.get(f"/api/jobs/{job_id}/report/download?format=pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert len(pdf_resp.content) > 100  # Non-empty PDF bytes

    # 4. Test HTML Download endpoint
    html_resp = client.get(f"/api/jobs/{job_id}/report/download?format=html")
    assert html_resp.status_code == 200
    assert "text/html" in html_resp.headers["content-type"]
    assert "Forest Intelligence Executive Report" in html_resp.text
