"""Expand game_stats table and add player_consistency_stats table

- Drops and recreates game_stats with full box score columns
- Creates player_consistency_stats for variance/volatility metrics

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-04-13 00:00:08.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, None] = 'i0j1k2l3m4n5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old game_stats table (it was unpopulated in practice)
    op.drop_table('game_stats')

    # Recreate with expanded schema
    op.create_table(
        'game_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=True),
        sa.Column('game_id', sa.String(20), nullable=False),
        sa.Column('game_date', sa.String(30), nullable=True),
        sa.Column('matchup', sa.String(20), nullable=True),
        sa.Column('wl', sa.String(1), nullable=True),

        # Box score
        sa.Column('minutes', sa.Numeric(6, 2), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True),
        sa.Column('assists', sa.Integer(), nullable=True),
        sa.Column('rebounds', sa.Integer(), nullable=True),
        sa.Column('offensive_rebounds', sa.Integer(), nullable=True),
        sa.Column('defensive_rebounds', sa.Integer(), nullable=True),
        sa.Column('steals', sa.Integer(), nullable=True),
        sa.Column('blocks', sa.Integer(), nullable=True),
        sa.Column('blocks_against', sa.Integer(), nullable=True),
        sa.Column('turnovers', sa.Integer(), nullable=True),
        sa.Column('personal_fouls', sa.Integer(), nullable=True),
        sa.Column('fouls_drawn', sa.Integer(), nullable=True),
        sa.Column('plus_minus', sa.Integer(), nullable=True),

        # Shooting
        sa.Column('fgm', sa.Integer(), nullable=True),
        sa.Column('fga', sa.Integer(), nullable=True),
        sa.Column('fg_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('fg3m', sa.Integer(), nullable=True),
        sa.Column('fg3a', sa.Integer(), nullable=True),
        sa.Column('fg3_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('ftm', sa.Integer(), nullable=True),
        sa.Column('fta', sa.Integer(), nullable=True),
        sa.Column('ft_pct', sa.Numeric(5, 3), nullable=True),

        # Milestones
        sa.Column('double_double', sa.Integer(), nullable=True),
        sa.Column('triple_double', sa.Integer(), nullable=True),

        # Fantasy
        sa.Column('fantasy_pts', sa.Numeric(6, 2), nullable=True),

        # Tracking - Offensive
        sa.Column('touches', sa.Integer(), nullable=True),
        sa.Column('front_court_touches', sa.Integer(), nullable=True),
        sa.Column('time_of_possession', sa.Numeric(6, 2), nullable=True),
        sa.Column('avg_seconds_per_touch', sa.Numeric(4, 2), nullable=True),
        sa.Column('avg_dribbles_per_touch', sa.Numeric(4, 2), nullable=True),
        sa.Column('points_per_touch', sa.Numeric(5, 3), nullable=True),
        sa.Column('paint_touches', sa.Integer(), nullable=True),
        sa.Column('post_touches', sa.Integer(), nullable=True),
        sa.Column('elbow_touches', sa.Integer(), nullable=True),

        # Tracking - Defensive
        sa.Column('deflections', sa.Integer(), nullable=True),
        sa.Column('contested_shots_2pt', sa.Integer(), nullable=True),
        sa.Column('contested_shots_3pt', sa.Integer(), nullable=True),
        sa.Column('charges_drawn', sa.Integer(), nullable=True),
        sa.Column('loose_balls_recovered', sa.Integer(), nullable=True),

        # Calculated
        sa.Column('offensive_metric', sa.Numeric(6, 2), nullable=True),
        sa.Column('defensive_metric', sa.Numeric(6, 2), nullable=True),
        sa.Column('game_score', sa.Numeric(6, 2), nullable=True),

        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_stats_player_id', 'game_stats', ['player_id'])
    op.create_index('ix_game_stats_game_id', 'game_stats', ['game_id'])
    op.create_index('ix_game_stats_season', 'game_stats', ['season'])

    # --- player_consistency_stats ---
    op.create_table(
        'player_consistency_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('games_used', sa.Integer(), nullable=True),

        # CV (coefficient of variation)
        sa.Column('pts_cv', sa.Numeric(6, 3), nullable=True),
        sa.Column('ast_cv', sa.Numeric(6, 3), nullable=True),
        sa.Column('reb_cv', sa.Numeric(6, 3), nullable=True),
        sa.Column('fantasy_cv', sa.Numeric(6, 3), nullable=True),
        sa.Column('game_score_cv', sa.Numeric(6, 3), nullable=True),

        # Standard deviations
        sa.Column('pts_std', sa.Numeric(6, 2), nullable=True),
        sa.Column('ast_std', sa.Numeric(6, 2), nullable=True),
        sa.Column('reb_std', sa.Numeric(6, 2), nullable=True),
        sa.Column('game_score_std', sa.Numeric(6, 2), nullable=True),

        # Game Score aggregates
        sa.Column('game_score_avg', sa.Numeric(6, 2), nullable=True),
        sa.Column('game_score_median', sa.Numeric(6, 2), nullable=True),
        sa.Column('game_score_max', sa.Numeric(6, 2), nullable=True),
        sa.Column('game_score_min', sa.Numeric(6, 2), nullable=True),

        # Boom/bust
        sa.Column('boom_games', sa.Integer(), nullable=True),
        sa.Column('bust_games', sa.Integer(), nullable=True),
        sa.Column('boom_pct', sa.Numeric(5, 3), nullable=True),
        sa.Column('bust_pct', sa.Numeric(5, 3), nullable=True),

        # Streaks
        sa.Column('best_streak', sa.Integer(), nullable=True),
        sa.Column('worst_streak', sa.Integer(), nullable=True),

        # Milestones
        sa.Column('dd_rate', sa.Numeric(5, 3), nullable=True),
        sa.Column('td_rate', sa.Numeric(5, 3), nullable=True),

        # Percentile
        sa.Column('consistency_score', sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_consistency_stats_player_id', 'player_consistency_stats', ['player_id'])
    op.create_index('ix_player_consistency_stats_season', 'player_consistency_stats', ['season'])


def downgrade() -> None:
    op.drop_table('player_consistency_stats')
    op.drop_table('game_stats')

    # Recreate old game_stats schema
    op.create_table(
        'game_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('game_id', sa.BigInteger(), nullable=False),
        sa.Column('game_date', sa.Date(), nullable=False),
        sa.Column('minutes', sa.Numeric(5, 2), nullable=True),
        sa.Column('points', sa.Integer(), nullable=True),
        sa.Column('assists', sa.Integer(), nullable=True),
        sa.Column('rebounds', sa.Integer(), nullable=True),
        sa.Column('steals', sa.Integer(), nullable=True),
        sa.Column('blocks', sa.Integer(), nullable=True),
        sa.Column('turnovers', sa.Integer(), nullable=True),
        sa.Column('touches', sa.Integer(), nullable=True),
        sa.Column('front_court_touches', sa.Integer(), nullable=True),
        sa.Column('time_of_possession', sa.Numeric(6, 2), nullable=True),
        sa.Column('avg_seconds_per_touch', sa.Numeric(4, 2), nullable=True),
        sa.Column('avg_dribbles_per_touch', sa.Numeric(4, 2), nullable=True),
        sa.Column('points_per_touch', sa.Numeric(5, 3), nullable=True),
        sa.Column('paint_touches', sa.Integer(), nullable=True),
        sa.Column('post_touches', sa.Integer(), nullable=True),
        sa.Column('elbow_touches', sa.Integer(), nullable=True),
        sa.Column('deflections', sa.Integer(), nullable=True),
        sa.Column('contested_shots_2pt', sa.Integer(), nullable=True),
        sa.Column('contested_shots_3pt', sa.Integer(), nullable=True),
        sa.Column('charges_drawn', sa.Integer(), nullable=True),
        sa.Column('loose_balls_recovered', sa.Integer(), nullable=True),
        sa.Column('offensive_metric', sa.Numeric(6, 2), nullable=True),
        sa.Column('defensive_metric', sa.Numeric(6, 2), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_stats_player_id', 'game_stats', ['player_id'])
    op.create_index('ix_game_stats_game_id', 'game_stats', ['game_id'])
