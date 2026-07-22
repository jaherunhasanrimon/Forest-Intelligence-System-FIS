from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

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


@app.get("/")
def read_root():
    return {"message": "Welcome to Forest Intelligence System API"}
