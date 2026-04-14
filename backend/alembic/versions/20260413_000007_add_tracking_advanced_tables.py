"""Add advanced tracking tables: speed/distance, passing, rebounding, defender distance, defensive play types

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-04-13 00:00:07.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i0j1k2l3m4n5'
down_revision: Union[str, None] = 'h9i0j1k2l3m4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- player_speed_distance ---
    op.create_table(
        'player_speed_distance',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('dist_miles', sa.Numeric(5, 2), nullable=True),
        sa.Column('dist_miles_off', sa.Numeric(5, 2), nullable=True),
        sa.Column('dist_miles_def', sa.Numeric(5, 2), nullable=True),
        sa.Column('avg_speed', sa.Numeric(5, 2), nullable=True),
        sa.Column('avg_speed_off', sa.Numeric(5, 2), nullable=True),
        sa.Column('avg_speed_def', sa.Numeric(5, 2), nullable=True),
        sa.Column('dist_feet', sa.Numeric(10, 2), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_speed_distance_player_id', 'player_speed_distance', ['player_id'])
    op.create_index('ix_player_speed_distance_season', 'player_speed_distance', ['season'])

    # --- player_passing_stats ---
    op.create_table(
        'player_passing_stats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('passes_made', sa.Numeric(6, 2), nullable=True),
        sa.Column('passes_received', sa.Numeric(6, 2), nullable=True),
        sa.Column('ft_ast', sa.Numeric(5, 2), nullable=True),
        sa.Column('secondary_ast', sa.Numeric(5, 2), nullable=True),
        sa.Column('potential_ast', sa.Numeric(5, 2), nullable=True),
        sa.Column('ast_points_created', sa.Numeric(6, 2), nullable=True),
        sa.Column('ast_adj', sa.Numeric(5, 2), nullable=True),
        sa.Column('ast_to_pass_pct', sa.Numeric(6, 4), nullable=True),
        sa.Column('ast_to_pass_pct_adj', sa.Numeric(6, 4), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_passing_stats_player_id', 'player_passing_stats', ['player_id'])
    op.create_index('ix_player_passing_stats_season', 'player_passing_stats', ['season'])

    # --- player_rebounding_tracking ---
    reb_cols = [
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
    ]
    for prefix in ('oreb', 'dreb', 'reb'):
        reb_cols.extend([
            sa.Column(prefix, sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_contest', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_uncontest', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_contest_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_chances', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_chance_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_chance_defer', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_chance_pct_adj', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'avg_{prefix}_dist', sa.Numeric(5, 2), nullable=True),
        ])
    reb_cols.extend([
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    ])
    op.create_table('player_rebounding_tracking', *reb_cols)
    op.create_index('ix_player_rebounding_tracking_player_id', 'player_rebounding_tracking', ['player_id'])
    op.create_index('ix_player_rebounding_tracking_season', 'player_rebounding_tracking', ['season'])

    # --- player_defender_distance_shooting ---
    dd_cols = [
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
    ]
    for prefix in ('very_tight', 'tight', 'open', 'wide_open'):
        dd_cols.extend([
            sa.Column(f'{prefix}_fga_freq', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_fgm', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_fga', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_fg_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_efg_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_fg3m', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_fg3a', sa.Numeric(5, 2), nullable=True),
            sa.Column(f'{prefix}_fg3_pct', sa.Numeric(5, 3), nullable=True),
        ])
    dd_cols.extend([
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    ])
    op.create_table('player_defender_distance_shooting', *dd_cols)
    op.create_index('ix_player_defender_distance_shooting_player_id', 'player_defender_distance_shooting', ['player_id'])
    op.create_index('ix_player_defender_distance_shooting_season', 'player_defender_distance_shooting', ['season'])

    # --- player_defensive_play_types ---
    dpt_cols = [
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(10), nullable=False),
        sa.Column('total_poss', sa.Integer(), nullable=True),
    ]
    for prefix in ('iso', 'pnr_ball_handler', 'post_up', 'spot_up', 'transition'):
        dpt_cols.extend([
            sa.Column(f'{prefix}_poss', sa.Integer(), nullable=True),
            sa.Column(f'{prefix}_pts', sa.Integer(), nullable=True),
            sa.Column(f'{prefix}_fgm', sa.Integer(), nullable=True),
            sa.Column(f'{prefix}_fga', sa.Integer(), nullable=True),
            sa.Column(f'{prefix}_ppp', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_fg_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_tov_pct', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_freq', sa.Numeric(5, 3), nullable=True),
            sa.Column(f'{prefix}_percentile', sa.Numeric(5, 3), nullable=True),
        ])
    dpt_cols.extend([
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    ])
    op.create_table('player_defensive_play_types', *dpt_cols)
    op.create_index('ix_player_defensive_play_types_player_id', 'player_defensive_play_types', ['player_id'])
    op.create_index('ix_player_defensive_play_types_season', 'player_defensive_play_types', ['season'])


def downgrade() -> None:
    op.drop_table('player_defensive_play_types')
    op.drop_table('player_defender_distance_shooting')
    op.drop_table('player_rebounding_tracking')
    op.drop_table('player_passing_stats')
    op.drop_table('player_speed_distance')
