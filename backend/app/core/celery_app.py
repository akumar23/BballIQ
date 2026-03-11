"""Celery application configuration for scheduled data refresh tasks."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "nba_stats",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.data_refresh", "app.tasks.metrics"],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution limits
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    # Task tracking
    task_track_started=True,
    task_acks_late=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time for long-running tasks
    # Result expiration
    result_expires=86400,  # 24 hours
)

# Celery Beat schedule for daily data refresh
celery_app.conf.beat_schedule = {
    "daily-data-refresh": {
        "task": "app.tasks.data_refresh.daily_data_refresh",
        "schedule": crontab(
            hour=settings.celery_schedule_hour,
            minute=settings.celery_schedule_minute,
        ),
        "options": {"queue": "data_refresh"},
    },
}

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.data_refresh.*": {"queue": "data_refresh"},
    "app.tasks.metrics.*": {"queue": "data_refresh"},
}
