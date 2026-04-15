"""Add touches breakdown and opponent shooting tables

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'k2l3m4n5o6p7'
down_revision: Union[str, None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TOUCH_KINDS = ("elbow_touch", "post_touch", "paint_touch")


def _touch_columns() -> list[sa.Column]:
    cols: list[sa.Column] = []
    for kind in TOUCH_KINDS:
        # "touches" field uses the plural form that matches the NBA API column
        plural = f"{kind}es" if kind.endswith("touch") else f"{kind}s"
        cols.append(sa.Column(plural, sa.Numeric(6, 2), nullable=True))
        for field in (
            "fgm",
            "fga",
            "ftm",
            "fta",
            "pts",
            "passes",
            "ast",
            "tov",
            "fouls",
        ):
            cols.append(sa.Column(f"{kind}_{field}", sa.Numeric(5, 2), nullable=True))
        cols.append(sa.Column(f"{kind}_fg_pct", sa.Numeric(5, 3), nullable=True))
        cols.append(sa.Column(f"{kind}_ft_pct", sa.Numeric(5, 3), nullable=True))
        cols.append(
            sa.Column(f"{kind}_pts_per_touch", sa.Numeric(5, 3), nullable=True)
        )
    return cols


def upgrade() -> None:
    # --- player_touches_breakdown ---
    op.create_table(
        'player_touches_breakdown',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        *_touch_columns(),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_player_touches_breakdown_player_id',
        'player_touches_breakdown',
        ['player_id'],
    )
    op.create_index(
        'ix_player_touches_breakdown_season',
        'player_touches_breakdown',
        ['season'],
    )

    # --- player_opponent_shooting ---
    op.create_table(
        'player_opponent_shooting',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('two_pt_games', sa.BigInteger(), nullable=True),
        sa.Column('two_pt_defended_fgm', sa.Numeric(6, 2), nullable=True),
        sa.Column('two_pt_defended_fga', sa.Numeric(6, 2), nullable=True),
        sa.Column('two_pt_defended_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('two_pt_normal_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('two_pt_pct_plusminus', sa.Numeric(5, 3), nullable=True),
        sa.Column('long_mid_defended_fgm', sa.Numeric(6, 2), nullable=True),
        sa.Column('long_mid_defended_fga', sa.Numeric(6, 2), nullable=True),
        sa.Column('long_mid_defended_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('long_mid_normal_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('long_mid_pct_plusminus', sa.Numeric(5, 3), nullable=True),
        sa.Column('lt_10ft_defended_fgm', sa.Numeric(6, 2), nullable=True),
        sa.Column('lt_10ft_defended_fga', sa.Numeric(6, 2), nullable=True),
        sa.Column('lt_10ft_defended_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('lt_10ft_normal_fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('lt_10ft_pct_plusminus', sa.Numeric(5, 3), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_player_opponent_shooting_player_id',
        'player_opponent_shooting',
        ['player_id'],
    )
    op.create_index(
        'ix_player_opponent_shooting_season',
        'player_opponent_shooting',
        ['season'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_player_opponent_shooting_season', table_name='player_opponent_shooting'
    )
    op.drop_index(
        'ix_player_opponent_shooting_player_id',
        table_name='player_opponent_shooting',
    )
    op.drop_table('player_opponent_shooting')

    op.drop_index(
        'ix_player_touches_breakdown_season',
        table_name='player_touches_breakdown',
    )
    op.drop_index(
        'ix_player_touches_breakdown_player_id',
        table_name='player_touches_breakdown',
    )
    op.drop_table('player_touches_breakdown')
