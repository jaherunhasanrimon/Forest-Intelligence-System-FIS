import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
# Import all ORM models to populate Base.metadata
from app.models.user import User
from app.models.aoi import AOI
from app.models.job import Job
from app.models.satellite_dataset import SatelliteDataset
from app.models.analysis_result import AnalysisResult
from app.models.report import Report

from sqlalchemy.pool import StaticPool

# Use SQLite in-memory database for isolated fast testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Create all tables in the SQLite test database
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables after the test session is completed
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def override_db_dependency():
    """
    Override the get_db dependency in the FastAPI application
    to direct queries to our isolated testing database session.
    """
    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
