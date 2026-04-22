"""Celery application configuration for scheduled data refresh tasks.

Observability hooks:

- :func:`configure_logging` and :func:`init_sentry` run at module import so
  every worker process (and the beat scheduler) emits JSON logs and reports
  to Sentry from the very first task.
- The ``task_prerun`` and ``task_postrun`` signals bind/clear
  ``task_id`` + ``task_name`` in structlog's contextvars so every log line
  produced inside a task body carries that context without the body
  needing to know about it.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery import Celery
from celery.schedules import crontab
from celery.signals import task_postrun, task_prerun

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry

# Configure observability at worker-boot / beat-boot time. Calling these
# from module scope (rather than waiting for a Celery signal) ensures any
# import-time errors in other modules are already JSON-logged and reported.
configure_logging()
init_sentry()

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

# Celery Beat schedule for daily data refresh.
# The task was explicitly renamed to the short name ``daily_data_refresh``
# (from the default dotted path) so both the task registry and beat schedule
# can use the stable, human-readable name. Signature is unchanged: ``season``
# is still the only argument.
celery_app.conf.beat_schedule = {
    "daily-data-refresh": {
        "task": "daily_data_refresh",
        "schedule": crontab(
            hour=settings.celery_schedule_hour,
            minute=settings.celery_schedule_minute,
        ),
        "options": {"queue": "data_refresh"},
    },
}

# Task routing. ``daily_data_refresh`` uses the explicit short name; the
# other refresh tasks still use their default dotted-path names so the
# wildcard below keeps matching them.
celery_app.conf.task_routes = {
    "daily_data_refresh": {"queue": "data_refresh"},
    "app.tasks.data_refresh.*": {"queue": "data_refresh"},
    "app.tasks.metrics.*": {"queue": "data_refresh"},
}


@task_prerun.connect
def _bind_task_context(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **_: Any,
) -> None:
    """Bind ``task_id`` / ``task_name`` into structlog contextvars.

    Every log line inside the task body (including those from deep in a
    service module using a plain stdlib logger) will include these fields
    when rendered, which makes the JSON logs actually navigable in Kibana /
    Loki / wherever they land.
    """
    task_name = getattr(task, "name", None) or (
        sender.name if sender is not None and hasattr(sender, "name") else None
    )
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task_name,
    )


@task_postrun.connect
def _clear_task_context(**_: Any) -> None:
    """Drop the bound context so the next task on this worker starts clean."""
    structlog.contextvars.clear_contextvars()
