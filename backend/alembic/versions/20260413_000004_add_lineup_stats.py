"""add lineup_stats table for 5-man lineup data

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-04-13 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, None] = 'e6f7g8h9i0j1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lineup_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('team_id', sa.BigInteger(), nullable=True),
        sa.Column('team_abbreviation', sa.String(10), nullable=True),
        sa.Column('lineup_id', sa.String(60), nullable=False),
        sa.Column('group_name', sa.String(200), nullable=True),
        sa.Column('player1_id', sa.BigInteger(), nullable=False),
        sa.Column('player2_id', sa.BigInteger(), nullable=False),
        sa.Column('player3_id', sa.BigInteger(), nullable=False),
        sa.Column('player4_id', sa.BigInteger(), nullable=False),
        sa.Column('player5_id', sa.BigInteger(), nullable=False),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('minutes', sa.Numeric(8, 2), nullable=True),
        sa.Column('plus_minus', sa.Numeric(8, 2), nullable=True),
        sa.Column('off_rating', sa.Numeric(6, 2), nullable=True),
        sa.Column('def_rating', sa.Numeric(6, 2), nullable=True),
        sa.Column('net_rating', sa.Numeric(6, 2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['player1_id'], ['players.id']),
        sa.ForeignKeyConstraint(['player2_id'], ['players.id']),
        sa.ForeignKeyConstraint(['player3_id'], ['players.id']),
        sa.ForeignKeyConstraint(['player4_id'], ['players.id']),
        sa.ForeignKeyConstraint(['player5_id'], ['players.id']),
    )
    op.create_index('ix_lineup_stats_season', 'lineup_stats', ['season'])
    op.create_index('ix_lineup_stats_lineup_id', 'lineup_stats', ['lineup_id'])
    op.create_index('ix_lineup_stats_player1_id', 'lineup_stats', ['player1_id'])
    op.create_index('ix_lineup_stats_player2_id', 'lineup_stats', ['player2_id'])
    op.create_index('ix_lineup_stats_player3_id', 'lineup_stats', ['player3_id'])
    op.create_index('ix_lineup_stats_player4_id', 'lineup_stats', ['player4_id'])
    op.create_index('ix_lineup_stats_player5_id', 'lineup_stats', ['player5_id'])


def downgrade() -> None:
    op.drop_table('lineup_stats')
