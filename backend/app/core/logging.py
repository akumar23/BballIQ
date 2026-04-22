"""Structured logging configuration.

Routes both ``logging``-emitted and ``structlog``-native records through a
shared processor chain, so every line — whether produced by FastAPI, Celery,
SQLAlchemy, or our own code — ends up as a single consistently-shaped JSON
object (or a human-readable console line when ``LOG_JSON=false``).

Two public helpers:

- :func:`configure_logging` — call once, as early as possible, from both
  ``app.main`` and ``app.core.celery_app``. Idempotent.
- :func:`get_logger` — thin passthrough to :func:`structlog.get_logger` so
  call-sites do not import structlog directly.

A ``contextvars`` processor is installed so request/task context bound via
``structlog.contextvars.bind_contextvars(...)`` (e.g. in middleware or Celery
signals) appears on every subsequent log line within that task/request.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars
from structlog.stdlib import ProcessorFormatter
from structlog.types import Processor

_CONFIGURED = False


def _env_flag(name: str, default: bool) -> bool:
    """Parse a truthy/falsy env var, falling back to ``default`` when unset."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _shared_processors() -> list[Processor]:
    """Processors applied to both structlog-native and stdlib-emitted records.

    The order matters: contextvars first so downstream processors see the
    bound context; renderer-specific processors (e.g. JSON/Console) are
    appended by the caller.
    """
    return [
        merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


def configure_logging() -> None:
    """Wire structlog + stdlib logging together. Safe to call multiple times.

    Reads ``LOG_LEVEL`` (default ``INFO``) and ``LOG_JSON`` (default ``true``)
    from the environment — we intentionally read the env directly here rather
    than importing ``app.core.config.settings`` so this function can be called
    before Pydantic settings are materialised (e.g. from ``celery_app`` module
    top-level) without triggering circular imports.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    json_logs = _env_flag("LOG_JSON", default=True)

    shared: list[Processor] = _shared_processors()

    # The final renderer differs between JSON and console modes; everything
    # else is shared. ``ProcessorFormatter.wrap_for_formatter`` hands off to
    # the formatter installed on the stdlib handler below.
    if json_logs:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[
            *shared,
            # Only applies to structlog.get_logger() loggers; stdlib-emitted
            # records are rendered by the ProcessorFormatter below.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
            if isinstance(logging.getLevelName(log_level), int)
            else logging.INFO
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib ``logging`` (used by third-party libs like SQLAlchemy,
    # Celery, uvicorn) through the same processor chain + renderer.
    formatter = ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            # Strip the ``_record`` and ``_from_structlog`` extras before render.
            ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace existing handlers so we don't double-log when Celery/uvicorn
    # install their own handlers later. We deliberately clear rather than
    # append so this remains idempotent on re-entry.
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Uvicorn / gunicorn set up their own access loggers with their own
    # handlers — let our root handler format their records too.
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error"):
        lg = logging.getLogger(noisy)
        lg.handlers.clear()
        lg.propagate = True

    _CONFIGURED = True


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a structlog BoundLogger bound to ``name`` with optional context."""
    return structlog.get_logger(name, **initial_values)
