import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 1. Initialize SQLite test database engine first
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 2. Patch SessionLocal in app.db BEFORE importing any modules that bind to it
import app.db
app.db.SessionLocal = TestingSessionLocal

# 3. Import app and models after patch
from app.db import Base, get_db
from app.main import app
from app.models.user import User
from app.models.aoi import AOI
from app.models.job import Job
from app.models.satellite_dataset import SatelliteDataset
from app.models.analysis_result import AnalysisResult
from app.models.report import Report
from app.tasks.celery_app import celery_app


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Configure Celery in eager mode for synchronous task execution during testing
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

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
