import pytest
import ee
from app.services.gee_service import authenticate_gee
from app.services.gee_script import (
    mask_s2_clouds,
    add_spectral_indices,
    create_10band_composite
)


@pytest.fixture(scope="module", autouse=True)
def init_gee():
    """Attempt to authenticate GEE before running GEE script tests."""
    try:
        authenticate_gee()
    except Exception as exc:
        pytest.skip(f"Skipping GEE script live tests (GEE Auth unavailable): {exc}")


def test_mask_s2_clouds_expression():
    """Test that mask_s2_clouds returns a valid ee.Image object."""
    img = ee.Image("COPERNICUS/S2_SR_HARMONIZED/20230101T000000_20230101T000000_T01MBN")
    masked = mask_s2_clouds(img)
    assert isinstance(masked, ee.Image)


def test_add_spectral_indices():
    """Test that add_spectral_indices computes NDVI and EVI bands."""
    img = ee.Image.constant([1000, 1000, 1000, 3000, 2000, 1000]).rename(
        ["B2", "B3", "B4", "B8", "B11", "B12"]
    )
    with_indices = add_spectral_indices(img)
    band_names = with_indices.bandNames().getInfo()
    assert "NDVI" in band_names
    assert "EVI" in band_names


def test_create_10band_composite_structure():
    """
    Integration test: Verify 10-band composite generation on Amazon test polygon.
    """
    test_geojson = {
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
    
    composite_image, metadata = create_10band_composite(
        test_geojson,
        start_date="2024-01-01",
        end_date="2024-03-01"
    )
    
    assert isinstance(composite_image, ee.Image)
    assert metadata["band_count"] == 10
    expected_bands = ['B2', 'B3', 'B4', 'B8', 'B11', 'B12', 'NDVI', 'EVI', 'VV', 'VH']
    assert metadata["band_names"] == expected_bands
