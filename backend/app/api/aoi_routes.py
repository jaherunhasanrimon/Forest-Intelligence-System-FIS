import math
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import shapely.geometry as sg
from shapely.validation import explain_validity

from app.db import get_db
from app.models.aoi import AOI
from app.models.job import Job
from app.models.user import User
from app.schemas.aoi import AOICreate, JobSubmissionResponse
from app.tasks.pipeline_tasks import process_aoi_pipeline

router = APIRouter(prefix="/aoi", tags=["AOI Selection"])


def calculate_approx_area_hectares(coordinates: list) -> float:
    """
    Calculate the area of a polygon in hectares using local planar projection.
    This avoids complex dependency compilation (like pyproj/PROJ) during local setup
    while remaining highly accurate for regional scale parcels.
    """
    if not coordinates or len(coordinates) < 3:
        return 0.0

    # Extract latitudes and longitudes
    lats = [pt[1] for pt in coordinates]
    lngs = [pt[0] for pt in coordinates]

    # Reference center latitude (mean)
    mean_lat_rad = math.radians(sum(lats) / len(lats))
    R = 6378137.0  # Earth's equatorial radius in meters

    # Project to local tangent plane (Orthographic projection approximation)
    projected = []
    for lng, lat in coordinates:
        x = R * math.radians(lng) * math.cos(mean_lat_rad)
        y = R * math.radians(lat)
        projected.append((x, y))

    # Shoelace formula to compute polygon area
    n = len(projected)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += projected[i][0] * projected[j][1]
        area -= projected[j][0] * projected[i][1]
    
    area_sq_meters = abs(area) / 2.0
    return area_sq_meters / 10000.0  # Convert to Hectares


def get_or_create_guest_user(db: Session) -> User:
    """
    Ensures a default Guest user exists in the database for Phase 1.
    This bypasses authentication block until Phase 2 is implemented.
    """
    guest = db.query(User).filter(User.email == "guest@forestintel.com").first()
    if not guest:
        guest = User(
            name="Guest Developer",
            email="guest@forestintel.com",
            password_hash="stub_hash",
            role="user"
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)
    return guest


@router.post("", response_model=JobSubmissionResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_aoi(payload: AOICreate, db: Session = Depends(get_db)):
    """
    Submit an Area of Interest (AOI) polygon along with a monitoring date range.
    Performs server-side validation using Shapely, calculates geographic area in hectares,
    and returns an asynchronous job token.
    """
    # 1. Server-side validation of GeoJSON structure using Shapely
    geojson_dict = payload.geometry.model_dump()
    try:
        geom = sg.shape(geojson_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Malformed geometry payload: {exc}"
        )

    # 2. Check for self-intersections or unclosed rings
    if not geom.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid geometry: {explain_validity(geom)}"
        )

    if geom.geom_type != "Polygon":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported geometry type: Expected Polygon, got {geom.geom_type}"
        )

    # 3. Calculate Hectares Area
    outer_coords = geojson_dict["coordinates"][0]
    area_ha = calculate_approx_area_hectares(outer_coords)

    # 4. Enforce server-side constraints (Pydantic models bypass validation on direct curl API submits)
    if area_ha > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Area exceeds maximum allowed boundary of 5000 ha (Selected: {area_ha:.2f} ha)"
        )

    if len(outer_coords) - 1 < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid geometry: Polygon must contain at least 3 vertices."
        )

    if payload.start_date >= payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid monitoring timeline: Start date must be earlier than End date."
        )

    # 5. Fetch guest user (Phase 1 auth stub)
    guest_user = get_or_create_guest_user(db)

    # 6. Save AOI to MySQL database
    db_aoi = AOI(
        user_id=guest_user.id,
        name=payload.name,
        geometry=geojson_dict,
        area_hectares=area_ha
    )
    db.add(db_aoi)
    db.commit()
    db.refresh(db_aoi)

    # 7. Create tracking Job row
    db_job = Job(
        aoi_id=db_aoi.id,
        user_id=guest_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="PENDING"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # 8. Trigger Celery task asynchronously
    process_aoi_pipeline.delay(db_job.id)

    # Return Job tracker details
    return {
        "job_id": db_job.id,
        "status": db_job.status,
        "aoi_id": db_aoi.id
    }
