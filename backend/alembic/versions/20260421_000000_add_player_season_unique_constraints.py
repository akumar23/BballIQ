"""Add (player_id, season) unique constraints on per-season stat tables

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-21 00:00:00.000000

Per-season fact tables previously had no uniqueness guarantee on
(player_id, season), which combined with SELECT-then-INSERT upsert patterns
could yield silent duplicates on task retries. This migration:

1. Deduplicates any existing ``(player_id, season)`` duplicates by keeping
   the row with the highest ``id`` per group. (For ``player_shot_zones``
   the group also includes ``zone``.)
2. Adds a ``UniqueConstraint`` per table so Postgres rejects duplicate
   writes going forward. The constraint also enables
   ``INSERT ... ON CONFLICT (player_id, season) DO UPDATE`` upserts used
   by the Celery refresh tasks.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m4n5o6p7q8r9"
down_revision: str | None = "l3m4n5o6p7q8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table_name, constraint_name, key_columns)
# For tables keyed only by (player_id, season), key_columns has two entries.
# For player_shot_zones, key_columns also includes "zone".
_CONSTRAINTS: list[tuple[str, str, tuple[str, ...]]] = [
    ("season_stats", "uq_season_stats_player_season", ("player_id", "season")),
    (
        "player_on_off_stats",
        "uq_player_on_off_stats_player_season",
        ("player_id", "season"),
    ),
    (
        "contextualized_impact",
        "uq_contextualized_impact_player_season",
        ("player_id", "season"),
    ),
    (
        "season_play_type_stats",
        "uq_season_play_type_stats_player_season",
        ("player_id", "season"),
    ),
    (
        "player_advanced_stats",
        "uq_player_advanced_stats_player_season",
        ("player_id", "season"),
    ),
    (
        "player_clutch_stats",
        "uq_player_clutch_stats_player_season",
        ("player_id", "season"),
    ),
    (
        "player_defensive_stats",
        "uq_player_defensive_stats_player_season",
        ("player_id", "season"),
    ),
    (
        "player_shot_zones",
        "uq_player_shot_zones_player_season_zone",
        ("player_id", "season", "zone"),
    ),
]


def _dedup_sql(table: str, columns: tuple[str, ...]) -> str:
    """Build a SQL statement that deletes duplicate rows, keeping MAX(id)."""
    join_conds = " AND ".join(f"a.{col} = b.{col}" for col in columns)
    return f"""
        DELETE FROM {table} a
        USING {table} b
        WHERE a.id < b.id
          AND {join_conds};
    """


def upgrade() -> None:
    conn = op.get_bind()
    for table, name, cols in _CONSTRAINTS:
        # 1. Dedup existing duplicate rows (keep row with MAX(id)).
        conn.exec_driver_sql(_dedup_sql(table, cols))
        # 2. Add the unique constraint.
        op.create_unique_constraint(name, table, list(cols))


def downgrade() -> None:
    for table, name, _cols in reversed(_CONSTRAINTS):
        op.drop_constraint(name, table, type_="unique")
