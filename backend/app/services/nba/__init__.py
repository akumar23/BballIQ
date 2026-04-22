"""Internal package layout for the NBA data client.

Callers should continue to import from :mod:`app.services.nba_data` — that
module is the stable public surface and re-exports everything from the
submodules below. This ``__init__`` is intentionally light to avoid a
circular import with ``app.services.nba_data`` during package bootstrap.
"""
