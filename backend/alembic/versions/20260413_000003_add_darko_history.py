"""add darko_history table

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-04-13 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7g8h9i0j1'
down_revision: Union[str, None] = 'd5e6f7g8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'darko_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('nba_id', sa.BigInteger(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('team_name', sa.String(50), nullable=True),
        sa.Column('age', sa.Numeric(4, 1), nullable=True),
        sa.Column('dpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('o_dpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('d_dpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('dpm_rank', sa.Integer(), nullable=True),
        sa.Column('o_dpm_rank', sa.Integer(), nullable=True),
        sa.Column('d_dpm_rank', sa.Integer(), nullable=True),
        sa.Column('box_odpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('box_ddpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('on_off_odpm', sa.Numeric(6, 2), nullable=True),
        sa.Column('on_off_ddpm', sa.Numeric(6, 2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_darko_history_nba_id', 'darko_history', ['nba_id'])
    op.create_index('ix_darko_history_season', 'darko_history', ['season'])


def downgrade() -> None:
    op.drop_table('darko_history')
