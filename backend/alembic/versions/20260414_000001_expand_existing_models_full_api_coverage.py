"""Expand existing models to fully cover NBA API endpoint fields

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-14 00:00:01.000000

Adds columns across seven existing tables so each row captures every useful
field returned by the NBA API endpoint feeding it. Models were updated first;
this migration is the DDL counterpart.

Tables touched:
- players (bio: height_inches, college)
- player_advanced_stats (E_* variants, pace_per40, poss)
- player_shooting_tracking (full Drives measure type)
- season_stats (touch granularity + hustle breakdowns)
- player_defender_distance_shooting (FG2 split per distance bucket)
- player_opponent_shooting (defender context: age, position, freq)
- player_defensive_stats (games_played, age, freq per bucket)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l3m4n5o6p7q8'
down_revision: Union[str, None] = 'k2l3m4n5o6p7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --------------------------------------------------------------------------- #
# Column specs grouped by table. Each entry is (name, type).
# --------------------------------------------------------------------------- #

PLAYERS_NEW = [
    ("height_inches", sa.BigInteger()),
    ("college", sa.String(length=120)),
]

ADVANCED_STATS_NEW = [
    ("e_off_rating", sa.Numeric(6, 1)),
    ("e_def_rating", sa.Numeric(6, 1)),
    ("e_net_rating", sa.Numeric(6, 1)),
    ("e_usg_pct", sa.Numeric(5, 3)),
    ("e_pace", sa.Numeric(6, 2)),
    ("pace_per40", sa.Numeric(6, 2)),
    ("poss", sa.BigInteger()),
]

SHOOTING_TRACKING_NEW = [
    ("drive_ftm", sa.Numeric(5, 2)),
    ("drive_fta", sa.Numeric(5, 2)),
    ("drive_ft_pct", sa.Numeric(5, 3)),
    ("drive_pts_pct", sa.Numeric(5, 3)),
    ("drive_passes", sa.Numeric(5, 2)),
    ("drive_passes_pct", sa.Numeric(5, 3)),
    ("drive_ast_pct", sa.Numeric(5, 3)),
    ("drive_tov_pct", sa.Numeric(5, 3)),
    ("drive_pf", sa.Numeric(5, 2)),
    ("drive_pf_pct", sa.Numeric(5, 3)),
]

SEASON_STATS_NEW = [
    ("avg_sec_per_touch", sa.Numeric(5, 2)),
    ("avg_drib_per_touch", sa.Numeric(5, 2)),
    ("pts_per_paint_touch", sa.Numeric(5, 3)),
    ("pts_per_post_touch", sa.Numeric(5, 3)),
    ("pts_per_elbow_touch", sa.Numeric(5, 3)),
    ("total_off_loose_balls_recovered", sa.Integer()),
    ("total_def_loose_balls_recovered", sa.Integer()),
    ("pct_loose_balls_off", sa.Numeric(5, 3)),
    ("pct_loose_balls_def", sa.Numeric(5, 3)),
    ("box_out_player_team_rebs", sa.Integer()),
    ("box_out_player_rebs", sa.Integer()),
    ("pct_box_outs_off", sa.Numeric(5, 3)),
    ("pct_box_outs_def", sa.Numeric(5, 3)),
    ("pct_box_outs_team_reb", sa.Numeric(5, 3)),
    ("pct_box_outs_reb", sa.Numeric(5, 3)),
]

OPPONENT_SHOOTING_NEW = [
    ("age", sa.Integer()),
    ("player_position", sa.String(length=10)),
    ("two_pt_freq", sa.Numeric(5, 3)),
    ("long_mid_freq", sa.Numeric(5, 3)),
    ("lt_10ft_freq", sa.Numeric(5, 3)),
]

DEFENSIVE_STATS_NEW = [
    ("games_played", sa.Integer()),
    ("age", sa.Integer()),
    ("overall_freq", sa.Numeric(5, 3)),
    ("rim_freq", sa.Numeric(5, 3)),
    ("three_pt_freq", sa.Numeric(5, 3)),
]


def _defender_distance_new_cols() -> list[tuple[str, sa.types.TypeEngine]]:
    """FG2 split + fg3a_freq per distance bucket."""
    cols: list[tuple[str, sa.types.TypeEngine]] = []
    for prefix in ("very_tight", "tight", "open", "wide_open"):
        cols.extend(
            [
                (f"{prefix}_fg2a_freq", sa.Numeric(5, 3)),
                (f"{prefix}_fg2m", sa.Numeric(5, 2)),
                (f"{prefix}_fg2a", sa.Numeric(5, 2)),
                (f"{prefix}_fg2_pct", sa.Numeric(5, 3)),
                (f"{prefix}_fg3a_freq", sa.Numeric(5, 3)),
            ]
        )
    return cols


TABLE_ADDITIONS: list[tuple[str, list[tuple[str, sa.types.TypeEngine]]]] = [
    ("players", PLAYERS_NEW),
    ("player_advanced_stats", ADVANCED_STATS_NEW),
    ("player_shooting_tracking", SHOOTING_TRACKING_NEW),
    ("season_stats", SEASON_STATS_NEW),
    ("player_defender_distance_shooting", _defender_distance_new_cols()),
    ("player_opponent_shooting", OPPONENT_SHOOTING_NEW),
    ("player_defensive_stats", DEFENSIVE_STATS_NEW),
]


def upgrade() -> None:
    for table, cols in TABLE_ADDITIONS:
        for name, col_type in cols:
            op.add_column(table, sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    for table, cols in reversed(TABLE_ADDITIONS):
        for name, _ in reversed(cols):
            op.drop_column(table, name)
