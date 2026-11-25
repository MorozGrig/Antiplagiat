"""Celery application configured to use Redis for broker and results."""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "author_materials_registry",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.workers.tasks_processing"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# shared_task decorators bind to the current/default app.
celery_app.set_default()
celery_app.autodiscover_tasks(["app.workers"], force=True)
