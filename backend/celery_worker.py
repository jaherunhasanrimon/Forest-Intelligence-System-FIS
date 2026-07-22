from app.tasks.celery_app import celery_app

# Import tasks so celery discovers them
from app.tasks import gee_export_tasks, analysis_tasks, pipeline_tasks  # noqa: F401

if __name__ == "__main__":
    celery_app.start()
