from celery import Celery
from src.core.logger import logger
from src.core.constants import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

# Create Celery app instance
celery_app = Celery(
    "tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["src.tasks"]
)

# Addtional config
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC+1",
    enable_utc=True,
    task_track_started=True,
)

logger.info(f"Celery app configured with broker: {CELERY_BROKER_URL}")