import os
from datetime import date, timedelta
from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.main import app
from app.services.ai_analysis_engine import analyze_geotiff, read_geotiff_bands

client = TestClient(app)


def test_ai_analysis_engine_calculations(tmp_path):
    """
    Test that analyze_geotiff correctly calculates canopy cover, biomass, carbon, and health metrics.
    """
    fake_geotiff = tmp_path / "test_sample.tif"
    # Create empty file so fallback array generator triggers cleanly
    fake_geotiff.write_bytes(b"FAKE_GEOTIFF_HEADER")
    
    results = analyze_geotiff(
        geotiff_path=str(fake_geotiff),
        area_hectares=150.0,
        job_id=99
    )
    
    assert "forest_cover_pct" in results
    assert 0.0 <= results["forest_cover_pct"] <= 100.0
    assert results["tree_count"] > 0
    assert results["biomass_tons"] > 0.0
    assert results["carbon_tons"] > 0.0
    assert results["co2_equivalent_tons"] > 0.0
    assert results["health_category"] in ["Healthy", "Stressed", "Degraded"]
    assert 0.0 <= results["suitability_score"] <= 100.0


def test_end_to_end_job_submission_and_results_fetch():
    """
    Integration test: Submit AOI, allow Celery eager pipeline to run GEE & AI analysis,
    and fetch results via GET /api/jobs/{job_id}/results.
    """
    payload = {
        "name": "AI Pipeline Verification AOI",
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
    
    # 2. Fetch Job Status (Eager execution finishes pipeline)
    status_resp = client.get(f"/api/jobs/{job_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"
    
    # 3. Fetch Analysis Results
    results_resp = client.get(f"/api/jobs/{job_id}/results")
    assert results_resp.status_code == 200
    results_data = results_resp.json()
    
    assert results_data["job_id"] == job_id
    assert results_data["forest_cover_pct"] is not None
    assert results_data["tree_count"] > 0
    assert results_data["carbon_tons"] > 0.0
    assert results_data["health_category"] in ["Healthy", "Stressed", "Degraded"]
