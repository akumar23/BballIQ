"""Observability wiring for Sentry error reporting.

Keep this module dependency-light: it must import cleanly whether or not
``SENTRY_DSN`` is configured. All Sentry integrations are imported at the
top so ``sentry-sdk`` is an import-time dependency, but none of them
actually run until :func:`init_sentry` is invoked.

The metrics (/metrics) endpoint is wired directly in :mod:`app.main` via
``prometheus-fastapi-instrumentator`` because it needs the FastAPI app
object at hand; this module is Sentry-only.
"""

from __future__ import annotations

import os

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration


def init_sentry() -> None:
    """Initialise Sentry when ``SENTRY_DSN`` is set; otherwise no-op.

    Called from both the FastAPI entrypoint and the Celery app module so
    web requests and background tasks report into the same Sentry project
    with the correct integration set. Safe to call multiple times — Sentry
    handles re-init by replacing its hub.

    Reads configuration directly from the environment rather than from
    ``app.core.config.settings`` so it can run before Pydantic settings
    are evaluated (important for Celery's worker-boot path).

    Environment variables:
        SENTRY_DSN: Required to activate; blank/unset makes this a no-op.
        SENTRY_ENV: Logical environment tag (e.g. "production", "staging").
        SENTRY_TRACES_SAMPLE_RATE: 0.0-1.0; defaults to 0.0 (traces disabled).
        GIT_SHA: Release identifier; typically injected by CI.
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        # Intentionally silent: local dev and CI usually don't have a DSN,
        # and logging a warning here would just be noise.
        return

    try:
        traces_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0"))
    except ValueError:
        traces_rate = 0.0

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(),
            CeleryIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        environment=os.getenv("SENTRY_ENV", "production"),
        release=os.getenv("GIT_SHA") or None,
        traces_sample_rate=traces_rate,
        # Never forward request bodies / user PII. This is a sports-stats
        # app with no PII, but defaulting to False is the safer posture.
        send_default_pii=False,
    )
