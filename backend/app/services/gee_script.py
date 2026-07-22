"""
Google Earth Engine — Sentinel-1 & Sentinel-2 Composite Processing Engine
===========================================================================

This module ports the Sentinel processing workflow to Python GEE API calls.
It builds a 10-band composite image clipped to an Area of Interest (AOI):

  Bands:
    1. B2    - Blue (10m)
    2. B3    - Green (10m)
    3. B4    - Red (10m)
    4. B8    - NIR (10m)
    5. B11   - SWIR1 (20m)
    6. B12   - SWIR2 (20m)
    7. NDVI  - Normalized Difference Vegetation Index
    8. EVI   - Enhanced Vegetation Index
    9. VV    - Sentinel-1 SAR Vertical/Vertical polarization
   10. VH    - Sentinel-1 SAR Vertical/Horizontal polarization
"""

import logging
from typing import Dict, Tuple, Any
import ee

logger = logging.getLogger(__name__)


def mask_s2_clouds(image: ee.Image) -> ee.Image:
    """
    Mask clouds in Sentinel-2 Surface Reflectance imagery using the QA60 bitmask band.
    """
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000.0)


def add_spectral_indices(image: ee.Image) -> ee.Image:
    """
    Compute NDVI and EVI spectral indices for Sentinel-2 imagery.
    """
    # NDVI = (NIR - RED) / (NIR + RED) = (B8 - B4) / (B8 + B4)
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    
    # EVI = 2.5 * ((NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1))
    evi = image.expression(
        "2.5 * ((NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLUE + 1.0))",
        {
            "NIR": image.select("B8"),
            "RED": image.select("B4"),
            "BLUE": image.select("B2")
        }
    ).rename("EVI")
    
    return image.addBands([ndvi, evi])


def build_sentinel2_composite(
    aoi_geom: ee.Geometry,
    start_date: str,
    end_date: str,
    max_cloud_pct: int = 30
) -> Tuple[ee.Image, int]:
    """
    Query, cloud-mask, and composite Sentinel-2 optical surface reflectance data.
    """
    s2_collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi_geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
    )
    
    scene_count = s2_collection.size().getInfo()
    logger.info("Sentinel-2 query returned %d scenes between %s and %s", scene_count, start_date, end_date)
    
    if scene_count == 0:
        raise ValueError(f"No Sentinel-2 imagery available for selected date range ({start_date} to {end_date}) below {max_cloud_pct}% cloud cover.")
    
    # Apply cloud mask and median composite
    masked_collection = s2_collection.map(mask_s2_clouds)
    optical_median = masked_collection.median().select(["B2", "B3", "B4", "B8", "B11", "B12"])
    
    # Add spectral vegetation indices
    optical_composite = add_spectral_indices(optical_median)
    return optical_composite, scene_count


def build_sentinel1_composite(
    aoi_geom: ee.Geometry,
    start_date: str,
    end_date: str
) -> Tuple[ee.Image, int]:
    """
    Query and process Sentinel-1 C-band Synthetic Aperture Radar (SAR) imagery.
    """
    s1_collection = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(aoi_geom)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("instrumentMode", "IW"))
    )
    
    scene_count = s1_collection.size().getInfo()
    logger.info("Sentinel-1 SAR query returned %d scenes between %s and %s", scene_count, start_date, end_date)
    
    if scene_count == 0:
        # Fallback to general S1 collection without IW strict filter if sparse
        s1_collection = (
            ee.ImageCollection("COPERNICUS/S1_GRD")
            .filterBounds(aoi_geom)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        )
        scene_count = s1_collection.size().getInfo()
        if scene_count == 0:
            logger.warning("No Sentinel-1 SAR scenes found for date range %s to %s. Creating zero SAR layer fallback.", start_date, end_date)
            # Dummy zero SAR image
            dummy = ee.Image.constant([0.0, 0.0]).rename(["VV", "VH"])
            return dummy, 0

    sar_median = s1_collection.select(["VV", "VH"]).median()
    
    # Focal mean speckle filter (3x3 kernel)
    sar_filtered = sar_median.focal_mean(radius=1.5, kernelType="square", units="pixels")
    return sar_filtered, scene_count


def create_10band_composite(
    geojson_geometry: Dict[str, Any],
    start_date: str,
    end_date: str
) -> Tuple[ee.Image, Dict[str, Any]]:
    """
    Create a unified 10-band composite image clipped to the input GeoJSON geometry.
    
    Returns:
        Tuple containing:
          - ee.Image with bands ['B2', 'B3', 'B4', 'B8', 'B11', 'B12', 'NDVI', 'EVI', 'VV', 'VH']
          - Metadata dictionary containing scene counts, bounds, and band names.
    """
    # 1. Convert GeoJSON to GEE Geometry
    aoi_geom = ee.Geometry(geojson_geometry)
    
    # 2. Build optical and SAR composites
    optical_img, s2_scenes = build_sentinel2_composite(aoi_geom, start_date, end_date)
    sar_img, s1_scenes = build_sentinel1_composite(aoi_geom, start_date, end_date)
    
    # 3. Stack into unified 10-band image
    composite_10band = optical_img.addBands(sar_img).clip(aoi_geom)
    
    band_names = composite_10band.bandNames().getInfo()
    logger.info("Successfully created 10-band composite with bands: %s", band_names)
    
    metadata = {
        "s2_scene_count": s2_scenes,
        "s1_scene_count": s1_scenes,
        "band_names": band_names,
        "band_count": len(band_names),
        "start_date": start_date,
        "end_date": end_date
    }
    
    return composite_10band, metadata
