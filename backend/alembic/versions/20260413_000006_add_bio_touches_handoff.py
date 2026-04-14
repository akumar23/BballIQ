"""Add player bio fields, touch tracking columns, and handoff play type

- Player: height, weight, jersey_number, birth_date, country, draft_year/round/number
- SeasonStats: total_paint_touches, total_post_touches, total_elbow_touches
- SeasonPlayTypeStats: handoff_poss/pts/fgm/fga/ppp/fg_pct/freq/ppp_percentile

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-04-13 00:00:06.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h9i0j1k2l3m4'
down_revision: Union[str, None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Player bio fields ---
    op.add_column('players', sa.Column('height', sa.String(10), nullable=True))
    op.add_column('players', sa.Column('weight', sa.BigInteger(), nullable=True))
    op.add_column('players', sa.Column('jersey_number', sa.String(5), nullable=True))
    op.add_column('players', sa.Column('birth_date', sa.String(20), nullable=True))
    op.add_column('players', sa.Column('country', sa.String(50), nullable=True))
    op.add_column('players', sa.Column('draft_year', sa.BigInteger(), nullable=True))
    op.add_column('players', sa.Column('draft_round', sa.BigInteger(), nullable=True))
    op.add_column('players', sa.Column('draft_number', sa.BigInteger(), nullable=True))

    # --- SeasonStats touch tracking ---
    op.add_column('season_stats', sa.Column('total_paint_touches', sa.Integer(), nullable=True))
    op.add_column('season_stats', sa.Column('total_post_touches', sa.Integer(), nullable=True))
    op.add_column('season_stats', sa.Column('total_elbow_touches', sa.Integer(), nullable=True))

    # --- SeasonPlayTypeStats handoff ---
    op.add_column('season_play_type_stats', sa.Column('handoff_poss', sa.Integer(), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_pts', sa.Integer(), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_fgm', sa.Integer(), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_fga', sa.Integer(), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_ppp', sa.Numeric(5, 3), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_fg_pct', sa.Numeric(5, 3), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_freq', sa.Numeric(5, 3), nullable=True))
    op.add_column('season_play_type_stats', sa.Column('handoff_ppp_percentile', sa.Integer(), nullable=True))


def downgrade() -> None:
    # --- SeasonPlayTypeStats handoff ---
    op.drop_column('season_play_type_stats', 'handoff_ppp_percentile')
    op.drop_column('season_play_type_stats', 'handoff_freq')
    op.drop_column('season_play_type_stats', 'handoff_fg_pct')
    op.drop_column('season_play_type_stats', 'handoff_ppp')
    op.drop_column('season_play_type_stats', 'handoff_fga')
    op.drop_column('season_play_type_stats', 'handoff_fgm')
    op.drop_column('season_play_type_stats', 'handoff_pts')
    op.drop_column('season_play_type_stats', 'handoff_poss')

    # --- SeasonStats touch tracking ---
    op.drop_column('season_stats', 'total_elbow_touches')
    op.drop_column('season_stats', 'total_post_touches')
    op.drop_column('season_stats', 'total_paint_touches')

    # --- Player bio fields ---
    op.drop_column('players', 'draft_number')
    op.drop_column('players', 'draft_round')
    op.drop_column('players', 'draft_year')
    op.drop_column('players', 'country')
    op.drop_column('players', 'birth_date')
    op.drop_column('players', 'jersey_number')
    op.drop_column('players', 'weight')
    op.drop_column('players', 'height')
