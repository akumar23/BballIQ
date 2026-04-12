"""add player_matchups and player_all_in_one_metrics tables

Revision ID: a2b3c4d5e6f7
Revises: 1fe3ed53b4de
Create Date: 2026-04-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '1fe3ed53b4de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'player_matchups',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        sa.Column('off_player_nba_id', sa.BigInteger(), nullable=False),
        sa.Column('off_player_name', sa.String(length=100), nullable=False),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('matchup_min', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('partial_poss', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('player_pts', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('team_pts', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fgm', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fga', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fg_pct', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('matchup_fg3m', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fg3a', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fg3_pct', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column('matchup_ftm', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_fta', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_ast', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_tov', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('matchup_blk', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('sfl', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('help_blk', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('help_fgm', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('help_fga', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('help_fg_pct', sa.Numeric(precision=5, scale=3), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_matchups_player_id', 'player_matchups', ['player_id'])
    op.create_index('ix_player_matchups_season', 'player_matchups', ['season'])
    op.create_index('ix_player_matchups_off_player_nba_id', 'player_matchups', ['off_player_nba_id'])

    op.create_table(
        'player_all_in_one_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        sa.Column('rapm', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('rapm_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('rapm_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('rpm', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('rpm_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('rpm_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('epm', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('epm_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('epm_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('raptor', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('raptor_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('raptor_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('lebron', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('lebron_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('lebron_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('darko', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('darko_offense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('darko_defense', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('data_sources', sa.Text(), nullable=True, comment='Comma-separated list of sources that provided data'),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_all_in_one_metrics_player_id', 'player_all_in_one_metrics', ['player_id'])
    op.create_index('ix_player_all_in_one_metrics_season', 'player_all_in_one_metrics', ['season'])


def downgrade() -> None:
    op.drop_index('ix_player_all_in_one_metrics_season', table_name='player_all_in_one_metrics')
    op.drop_index('ix_player_all_in_one_metrics_player_id', table_name='player_all_in_one_metrics')
    op.drop_table('player_all_in_one_metrics')

    op.drop_index('ix_player_matchups_off_player_nba_id', table_name='player_matchups')
    op.drop_index('ix_player_matchups_season', table_name='player_matchups')
    op.drop_index('ix_player_matchups_player_id', table_name='player_matchups')
    op.drop_table('player_matchups')
