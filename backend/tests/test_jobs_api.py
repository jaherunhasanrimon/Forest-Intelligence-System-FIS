from datetime import date, timedelta
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_jobs_empty():
    """
    Test listing jobs when no jobs exist (or list all current jobs).
    """
    response = client.get("/api/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_submit_aoi_triggers_job_and_poll():
    """
    Integration test: Submitting an AOI should create a Job, and we should be
    able to poll the job status and fetch listing info.
    """
    # 1. Submit AOI
    payload = {
        "name": "Orchestration Test Parcel",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)),
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
    
    submit_response = client.post("/api/aoi", json=payload)
    assert submit_response.status_code == 202
    submit_data = submit_response.json()
    job_id = submit_data["job_id"]
    
    # 2. Poll Status
    status_response = client.get(f"/api/jobs/{job_id}/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] == "COMPLETED"
    assert "elapsed_seconds" in status_data

    # 3. Check job shows up in List
    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    job_ids = [j["id"] for j in list_response.json()]
    assert job_id in job_ids

    # 4. Clean up / Cancel Job
    delete_response = client.delete(f"/api/jobs/{job_id}")
    assert delete_response.status_code == 204

    # 5. Verify deleted
    verify_response = client.get(f"/api/jobs/{job_id}/status")
    assert verify_response.status_code == 404
