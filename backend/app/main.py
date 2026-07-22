import os
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models.job import Job
from app.api.aoi_routes import router as aoi_router
from app.api.job_routes import router as job_router

app = FastAPI(
    title="Forest Intelligence System API",
    description="Backend API services for automated satellite data acquisition and forest analysis",
    version="1.0.0",
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to trusted origins in staging/production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve directories relative to main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Mount Static assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates Configuration
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Include Router Modules
app.include_router(aoi_router, prefix="/api")
app.include_router(job_router, prefix="/api")


@app.get("/health")
def health_check():
    """
    Service health check endpoint.
    """
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "api_version": "1.0.0"
    }


# ---------------------------------------------------------------------------
# HTML Page Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def get_map_selector(request: Request):
    """
    Serves the interactive Google Map AOI selector page.
    """
    return templates.TemplateResponse(
        "aoi_selector.html",
        {
            "request": request,
            "active_page": "aoi",
            "maps_api_key": settings.GOOGLE_MAPS_API_KEY
        }
    )


@app.get("/jobs", response_class=HTMLResponse)
def get_jobs_list(request: Request, db: Session = Depends(get_db)):
    """
    Serves the dashboard table showing all async pipeline runs.
    """
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return templates.TemplateResponse(
        "jobs_list.html",
        {
            "request": request,
            "active_page": "jobs",
            "jobs": jobs
        }
    )
