import logging
import redis
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

# Check if Redis broker is reachable locally
task_always_eager = False
try:
    r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=1)
    r.ping()
    logger.info("Successfully connected to Redis broker at %s", settings.REDIS_URL)
except Exception as exc:
    task_always_eager = True
    logger.warning("Redis broker unavailable (%s). Falling back to Celery eager execution mode.", exc)

celery_app = Celery(
    "fis_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_always_eager=task_always_eager,
    task_eager_propagates=task_always_eager,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max execution time for a job
)
