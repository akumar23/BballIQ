"""fastapi-cache2 wiring: init helper and a db-session-aware key builder.

The default ``default_key_builder`` from ``fastapi_cache`` hashes the full
``kwargs`` dict as part of the cache key. In our app, endpoint kwargs include
the ``db: Session = Depends(get_db)`` dependency, whose repr is the object's
memory address and thus differs on every request. That would make every
request a cache miss. We strip DB-session arguments (and anything else that
shouldn't affect the response) before hashing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response

# Kwargs we want to exclude from the cache key. Extend as new per-request
# dependencies show up (e.g. ``user`` once auth lands — at which point you
# probably want to *vary* on user instead, i.e. remove from this set and
# encode a stable identifier into the key).
_IGNORED_KWARGS: frozenset[str] = frozenset({"db"})


def request_key_builder(
    func: Callable[..., Any],
    namespace: str = "",
    *,
    request: Request | None = None,
    response: Response | None = None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """Build a stable cache key from the request URL and non-DB kwargs.

    Using ``request.url.path`` + sorted query params gives us a
    human-readable, collision-resistant key that naturally varies on query
    params (``season``, ``limit``, ``offset``, ``sort_by``, etc.) without
    depending on the opaque repr of the Session dependency.
    """
    # Prefer the raw request URL when available — it already captures path
    # params and sorted query strings deterministically.
    if request is not None:
        key_source = (
            f"{request.method}:{request.url.path}?"
            f"{sorted(request.query_params.multi_items())}"
        )
    else:
        # Fallback: hash filtered kwargs (skip DB session and any object
        # whose repr includes a memory address, which is a proxy for
        # "non-stable identity").
        filtered: dict[str, Any] = {
            k: v
            for k, v in kwargs.items()
            if k not in _IGNORED_KWARGS and not isinstance(v, Session)
        }
        key_source = f"{func.__module__}:{func.__name__}:{args}:{filtered}"

    digest = hashlib.md5(key_source.encode()).hexdigest()  # noqa: S324
    return f"{namespace}:{func.__name__}:{digest}"
