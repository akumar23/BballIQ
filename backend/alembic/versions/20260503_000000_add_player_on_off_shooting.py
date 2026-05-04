"""Add player_on_off_shooting table

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-05-03 00:00:00.000000

Adds team-shooting on/off splits sourced from
``TeamPlayerOnOffSummary(measure_type_detailed_defense="Shooting")``.
This table is the primary input for the new gravity index's
``teammate_lift`` component (team eFG% lift + share-of-open-3 lift).

Schema mirrors ``player_on_off_stats``: keyed ``(player_id, season)``
with a unique constraint to enable ``ON CONFLICT DO UPDATE`` upserts in
the impact-data refresh task.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "o7p8q9r0s1t2"
down_revision: str | None = "n6o7p8q9r0s1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_on_off_shooting",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("season", sa.String(10), nullable=False),
        # Sample-size columns
        sa.Column("on_court_minutes", sa.Numeric(8, 2), nullable=True),
        sa.Column("off_court_minutes", sa.Numeric(8, 2), nullable=True),
        # eFG%
        sa.Column("on_court_team_efg", sa.Numeric(5, 3), nullable=True),
        sa.Column("off_court_team_efg", sa.Numeric(5, 3), nullable=True),
        sa.Column("team_efg_diff", sa.Numeric(5, 3), nullable=True),
        # Open 3 frequency
        sa.Column("on_court_team_open3_freq", sa.Numeric(5, 3), nullable=True),
        sa.Column("off_court_team_open3_freq", sa.Numeric(5, 3), nullable=True),
        sa.Column("team_open3_freq_diff", sa.Numeric(5, 3), nullable=True),
        # Wide-open 3 frequency
        sa.Column("on_court_team_wide_open3_freq", sa.Numeric(5, 3), nullable=True),
        sa.Column("off_court_team_wide_open3_freq", sa.Numeric(5, 3), nullable=True),
        sa.Column("team_wide_open3_freq_diff", sa.Numeric(5, 3), nullable=True),
        # Catch-and-shoot share of team FGA
        sa.Column("on_court_team_catch_shoot_share", sa.Numeric(5, 3), nullable=True),
        sa.Column("off_court_team_catch_shoot_share", sa.Numeric(5, 3), nullable=True),
        sa.Column("team_catch_shoot_share_diff", sa.Numeric(5, 3), nullable=True),
        # Pull-up share of team FGA
        sa.Column("on_court_team_pullup_share", sa.Numeric(5, 3), nullable=True),
        sa.Column("off_court_team_pullup_share", sa.Numeric(5, 3), nullable=True),
        sa.Column("team_pullup_share_diff", sa.Numeric(5, 3), nullable=True),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "player_id",
            "season",
            name="uq_player_on_off_shooting_player_season",
        ),
    )
    op.create_index(
        "ix_player_on_off_shooting_player_id",
        "player_on_off_shooting",
        ["player_id"],
    )
    op.create_index(
        "ix_player_on_off_shooting_season",
        "player_on_off_shooting",
        ["season"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_on_off_shooting_season", table_name="player_on_off_shooting"
    )
    op.drop_index(
        "ix_player_on_off_shooting_player_id", table_name="player_on_off_shooting"
    )
    op.drop_table("player_on_off_shooting")
