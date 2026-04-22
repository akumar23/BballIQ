"""SQLAlchemy engine and session factory.

Pool tuning values are hardcoded here (not surfaced on ``Settings``) because
they are infrastructure-shaped — they follow from the worker/DB topology,
not from user-facing configuration. Revisit if the worker count changes
materially or if Postgres connection limits get tightened.

- ``pool_pre_ping=True``: issues a cheap ``SELECT 1`` on checkout so stale
  connections (closed by PG/LB after idle timeouts) are recycled transparently
  rather than surfacing as ``OperationalError`` on the first query.
- ``pool_recycle=1800`` (30 min): proactively recycles connections below
  typical PG ``idle_session_timeout`` / LB idle-kill windows.
- ``pool_size=10, max_overflow=20``: 10 long-lived + up to 20 burst = 30
  concurrent connections per process. Sized for the current uvicorn
  worker/Celery pool so we stay well under PG's default ``max_connections``.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
