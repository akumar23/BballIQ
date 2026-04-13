"""add peak_rapm, raptor_history, mamba_history, forced_turnovers tables

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-04-13 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d5e6f7g8h9'
down_revision: Union[str, None] = 'b3c4d5e6f7g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Peak RAPM
    op.create_table(
        'peak_rapm',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('nba_id', sa.BigInteger(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('dataset', sa.String(30), nullable=False),
        sa.Column('orapm', sa.Numeric(8, 4), nullable=True),
        sa.Column('drapm', sa.Numeric(8, 4), nullable=True),
        sa.Column('rapm', sa.Numeric(8, 4), nullable=True),
        sa.Column('orapm_rank', sa.Integer(), nullable=True),
        sa.Column('drapm_rank', sa.Integer(), nullable=True),
        sa.Column('rapm_rank', sa.Integer(), nullable=True),
        sa.Column('current', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_peak_rapm_nba_id', 'peak_rapm', ['nba_id'])
    op.create_index('ix_peak_rapm_dataset', 'peak_rapm', ['dataset'])

    # RAPTOR history
    op.create_table(
        'raptor_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('nba_id', sa.String(20), nullable=False),
        sa.Column('season', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('possessions', sa.Integer(), nullable=True),
        sa.Column('raptor_offense', sa.Numeric(6, 2), nullable=True),
        sa.Column('raptor_defense', sa.Numeric(6, 2), nullable=True),
        sa.Column('raptor_total', sa.Numeric(6, 2), nullable=True),
        sa.Column('war_total', sa.Numeric(10, 6), nullable=True),
        sa.Column('o_raptor_rank', sa.Integer(), nullable=True),
        sa.Column('d_raptor_rank', sa.Integer(), nullable=True),
        sa.Column('raptor_rank', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_raptor_history_nba_id', 'raptor_history', ['nba_id'])
    op.create_index('ix_raptor_history_season', 'raptor_history', ['season'])
    op.create_index('ix_raptor_history_player_name', 'raptor_history', ['player_name'])

    # MAMBA history
    op.create_table(
        'mamba_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('nba_id', sa.BigInteger(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('minutes', sa.Numeric(8, 1), nullable=True),
        sa.Column('o_mamba', sa.Numeric(8, 4), nullable=True),
        sa.Column('d_mamba', sa.Numeric(8, 4), nullable=True),
        sa.Column('mamba', sa.Numeric(8, 4), nullable=True),
        sa.Column('o_mamba_rank', sa.Integer(), nullable=True),
        sa.Column('d_mamba_rank', sa.Integer(), nullable=True),
        sa.Column('mamba_rank', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mamba_history_nba_id', 'mamba_history', ['nba_id'])
    op.create_index('ix_mamba_history_year', 'mamba_history', ['year'])

    # Forced turnovers
    op.create_table(
        'forced_turnovers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('nba_id', sa.BigInteger(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('dtov', sa.Numeric(6, 2), nullable=True),
        sa.Column('diff', sa.Numeric(6, 2), nullable=True),
        sa.Column('total_def_poss', sa.Integer(), nullable=True),
        sa.Column('weighted_avg_rftov', sa.Numeric(6, 2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_forced_turnovers_nba_id', 'forced_turnovers', ['nba_id'])


def downgrade() -> None:
    op.drop_table('forced_turnovers')
    op.drop_table('mamba_history')
    op.drop_table('raptor_history')
    op.drop_table('peak_rapm')
