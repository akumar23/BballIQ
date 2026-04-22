"""Add game_stats composite index and pg_trgm-backed player name search

Revision ID: n6o7p8q9r0s1
Revises: m4n5o6p7q8r9
Create Date: 2026-04-22 00:00:00.000000

Two tightly-related read-path performance improvements bundled into a single
migration. Both are index-only; neither changes any table schema or data.

1. Composite index ``ix_game_stats_player_season_date`` on
   ``game_stats(player_id, season, game_date DESC)`` backs the per-player
   gamelog endpoint (``GET /api/players/{id}/games``) which filters by
   ``player_id`` + ``season`` and orders by ``game_date DESC``. Prior
   migrations only indexed these columns individually, forcing the planner
   into bitmap-heap scans + a top-N sort on every call.

2. ``pg_trgm`` extension + GIN trigram index on ``players.name`` backs the
   fuzzy search endpoint (``GET /api/players/search``). ``CREATE EXTENSION``
   is idempotent and cheap; the GIN index is the real work here. Trigram
   matching lets the API return useful results for typos and partial names
   without a full table scan.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n6o7p8q9r0s1"
down_revision: str | None = "m4n5o6p7q8r9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Composite index for the gamelog query.
    op.create_index(
        "ix_game_stats_player_season_date",
        "game_stats",
        ["player_id", "season", sa.text("game_date DESC")],
        postgresql_using="btree",
    )

    # 2. pg_trgm for fuzzy player-name search. Both statements are idempotent
    #    enough to re-run in a broken-migration rollback scenario.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_players_name_trgm "
        "ON players USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    # Drop in reverse order. We do NOT drop the extension itself — other
    # objects in the database might depend on it and extensions are
    # database-wide, not table-scoped.
    op.execute("DROP INDEX IF EXISTS ix_players_name_trgm")
    op.drop_index("ix_game_stats_player_season_date", table_name="game_stats")
