"""Current NBA season helpers.

The NBA season crosses a calendar year boundary. A season labelled
``2024-25`` starts in October 2024 and ends in June 2025. This module
provides a single source of truth for deriving the "current" season so
that both FastAPI routes and Celery tasks stay in sync.

Rules:
    - On or after October 1st of year ``Y``: season is ``{Y}-{Y+1 last 2 digits}``.
    - Before October 1st of year ``Y``: season is ``{Y-1}-{Y last 2 digits}``
      (covers both the January-June tail of the prior season and the
      July-September offseason).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

__all__ = ["get_current_season", "current_season_dep", "season_for_date"]

_SEASON_ROLLOVER_MONTH = 10
_SEASON_ROLLOVER_DAY = 1


def season_for_date(today: date) -> str:
    """Return the NBA season string active for a given calendar date.

    Args:
        today: The reference date. Use ``datetime.now(timezone.utc).date()`` to
            get the current season.

    Returns:
        Season string of the form ``"YYYY-YY"`` (e.g. ``"2024-25"``).
    """
    if (today.month, today.day) >= (_SEASON_ROLLOVER_MONTH, _SEASON_ROLLOVER_DAY):
        start_year = today.year
    else:
        start_year = today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def get_current_season() -> str:
    """Return the currently active NBA season in ``YYYY-YY`` format.

    Uses UTC so the value is deterministic across deployments regardless of
    the local timezone of the worker or web process.
    """
    return season_for_date(datetime.now(UTC).date())


def current_season_dep() -> str:
    """FastAPI dependency wrapper that returns the current season.

    Intended for use with ``Depends(current_season_dep)`` on endpoints that
    do not expose a ``season`` query parameter.
    """
    return get_current_season()
