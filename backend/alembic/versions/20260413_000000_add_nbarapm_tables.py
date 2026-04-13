"""add nbarapm.com tables: rapm_windows, big_board, six_factor_rapm + laker/mamba columns

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add LAKER and MAMBA columns to existing all_in_one_metrics table
    op.add_column('player_all_in_one_metrics', sa.Column('laker', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('laker_offense', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('laker_defense', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('mamba', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('mamba_offense', sa.Numeric(6, 2), nullable=True))
    op.add_column('player_all_in_one_metrics', sa.Column('mamba_defense', sa.Numeric(6, 2), nullable=True))

    # Create player_rapm_windows table
    op.create_table(
        'player_rapm_windows',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        # Timedecay
        sa.Column('timedecay_orapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('timedecay_drapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('timedecay_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('timedecay_orapm_rank', sa.Integer(), nullable=True),
        sa.Column('timedecay_drapm_rank', sa.Integer(), nullable=True),
        sa.Column('timedecay_rapm_rank', sa.Integer(), nullable=True),
        # 2-year
        sa.Column('two_year_orapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('two_year_drapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('two_year_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('two_year_orapm_rank', sa.Integer(), nullable=True),
        sa.Column('two_year_drapm_rank', sa.Integer(), nullable=True),
        sa.Column('two_year_rapm_rank', sa.Integer(), nullable=True),
        # 3-year
        sa.Column('three_year_orapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('three_year_drapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('three_year_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('three_year_orapm_rank', sa.Integer(), nullable=True),
        sa.Column('three_year_drapm_rank', sa.Integer(), nullable=True),
        sa.Column('three_year_rapm_rank', sa.Integer(), nullable=True),
        # 4-year
        sa.Column('four_year_orapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('four_year_drapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('four_year_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('four_year_orapm_rank', sa.Integer(), nullable=True),
        sa.Column('four_year_drapm_rank', sa.Integer(), nullable=True),
        sa.Column('four_year_rapm_rank', sa.Integer(), nullable=True),
        # 5-year
        sa.Column('five_year_orapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('five_year_drapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('five_year_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('five_year_orapm_rank', sa.Integer(), nullable=True),
        sa.Column('five_year_drapm_rank', sa.Integer(), nullable=True),
        sa.Column('five_year_rapm_rank', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_rapm_windows_player_id', 'player_rapm_windows', ['player_id'])
    op.create_index('ix_player_rapm_windows_season', 'player_rapm_windows', ['season'])

    # Create player_big_board table
    op.create_table(
        'player_big_board',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('player_id', sa.BigInteger(), nullable=False),
        sa.Column('season', sa.String(length=10), nullable=False),
        sa.Column('position', sa.String(10), nullable=True),
        sa.Column('offensive_archetype', sa.String(50), nullable=True),
        sa.Column('age', sa.Numeric(4, 1), nullable=True),
        sa.Column('games_played', sa.Integer(), nullable=True),
        sa.Column('minutes', sa.Numeric(8, 1), nullable=True),
        sa.Column('mpg', sa.Numeric(5, 2), nullable=True),
        sa.Column('salary', sa.Numeric(12, 2), nullable=True),
        # Scoring efficiency
        sa.Column('pts_per_75', sa.Numeric(6, 2), nullable=True),
        sa.Column('ts_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('ts_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('relative_ts', sa.Numeric(6, 2), nullable=True),
        sa.Column('relative_ts_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('mod_ts', sa.Numeric(6, 2), nullable=True),
        sa.Column('ts_added_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('ts_added_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('tsa_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('tsa_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        # Shooting splits
        sa.Column('fg2_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('fg2_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('fg2a_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('fg3_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('fg3_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('fg3a_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('three_point_rate', sa.Numeric(6, 2), nullable=True),
        sa.Column('ft_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('ft_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('fta_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('ftr', sa.Numeric(6, 2), nullable=True),
        sa.Column('ftr_percentile', sa.Numeric(4, 2), nullable=True),
        # Catch-and-shoot / pull-up
        sa.Column('cs_3pa', sa.Numeric(6, 2), nullable=True),
        sa.Column('cs_3pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('pu_3pa', sa.Numeric(6, 2), nullable=True),
        sa.Column('pu_3pct', sa.Numeric(6, 2), nullable=True),
        # Passing
        sa.Column('assists_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('assists_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('potential_assists_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('at_rim_assists_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('mid_assists_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('three_pt_assists_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('assist_efg', sa.Numeric(4, 2), nullable=True),
        sa.Column('assist_efg_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('on_ball_time_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('on_ball_time_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('bad_pass_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('bad_pass_tov_per_100', sa.Numeric(6, 2), nullable=True),
        # Turnovers
        sa.Column('scoring_tov_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('scoring_tov_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('scoring_tovs_per_100', sa.Numeric(6, 2), nullable=True),
        # Defense
        sa.Column('dfga_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('dfga_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('dif_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('dif_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('stops_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('stops_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('relative_stops_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('blocks_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('steals_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('offd_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('points_saved_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('points_saved_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('forced_tov_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('forced_tov_per_100_percentile', sa.Numeric(4, 2), nullable=True),
        # Rim defense
        sa.Column('rim_dfga_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_dif_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_dif_pct_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('rim_points_saved_per_100', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_freq_on', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_freq_onoff', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_acc_on', sa.Numeric(6, 2), nullable=True),
        sa.Column('rim_acc_onoff', sa.Numeric(6, 2), nullable=True),
        # Rebounding
        sa.Column('prob_off_rebounded', sa.Numeric(6, 2), nullable=True),
        sa.Column('self_oreb_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('teammate_miss_oreb_pct', sa.Numeric(6, 2), nullable=True),
        # Play type impact
        sa.Column('playtype_rppp', sa.Numeric(8, 6), nullable=True),
        sa.Column('playtype_rppp_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('playtype_ts_rppp', sa.Numeric(8, 6), nullable=True),
        sa.Column('playtype_tov_rppp', sa.Numeric(8, 6), nullable=True),
        sa.Column('playtype_diff', sa.Numeric(6, 2), nullable=True),
        sa.Column('playtype_diff_percentile', sa.Numeric(4, 2), nullable=True),
        sa.Column('playtype_adj_rppp', sa.Numeric(8, 6), nullable=True),
        sa.Column('pt_adj_rts', sa.Numeric(6, 2), nullable=True),
        # Shooting context
        sa.Column('first_chance_pct', sa.Numeric(6, 2), nullable=True),
        sa.Column('second_fg_created_per_100', sa.Numeric(6, 2), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_player_big_board_player_id', 'player_big_board', ['player_id'])
    op.create_index('ix_player_big_board_season', 'player_big_board', ['season'])

    # Create six_factor_rapm table
    op.create_table(
        'six_factor_rapm',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('nba_id', sa.BigInteger(), nullable=False),
        sa.Column('player_name', sa.String(100), nullable=False),
        sa.Column('year_interval', sa.String(5), nullable=False),
        sa.Column('latest_year', sa.Integer(), nullable=False),
        sa.Column('off_poss', sa.Integer(), nullable=True),
        # Overall RAPM
        sa.Column('off_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('def_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('ovr_rapm', sa.Numeric(6, 2), nullable=True),
        sa.Column('off_rapm_rank', sa.Integer(), nullable=True),
        sa.Column('def_rapm_rank', sa.Integer(), nullable=True),
        sa.Column('ovr_rapm_rank', sa.Integer(), nullable=True),
        # Offensive factors
        sa.Column('sc_off_ts', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_off_ts_rank', sa.Integer(), nullable=True),
        sa.Column('sc_off_tov', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_off_tov_rank', sa.Integer(), nullable=True),
        sa.Column('sc_off_reb', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_off_reb_rank', sa.Integer(), nullable=True),
        # Defensive factors
        sa.Column('sc_def_ts', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_def_ts_rank', sa.Integer(), nullable=True),
        sa.Column('sc_def_tov', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_def_tov_rank', sa.Integer(), nullable=True),
        sa.Column('sc_def_reb', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_def_reb_rank', sa.Integer(), nullable=True),
        # Possession factor
        sa.Column('sc_poss', sa.Numeric(6, 2), nullable=True),
        sa.Column('sc_poss_rank', sa.Integer(), nullable=True),
        # Residuals
        sa.Column('off_diff', sa.Numeric(6, 2), nullable=True),
        sa.Column('def_diff', sa.Numeric(6, 2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_six_factor_rapm_nba_id', 'six_factor_rapm', ['nba_id'])
    op.create_index('ix_six_factor_rapm_year_interval', 'six_factor_rapm', ['year_interval'])


def downgrade() -> None:
    op.drop_table('six_factor_rapm')
    op.drop_table('player_big_board')
    op.drop_table('player_rapm_windows')
    op.drop_column('player_all_in_one_metrics', 'mamba_defense')
    op.drop_column('player_all_in_one_metrics', 'mamba_offense')
    op.drop_column('player_all_in_one_metrics', 'mamba')
    op.drop_column('player_all_in_one_metrics', 'laker_defense')
    op.drop_column('player_all_in_one_metrics', 'laker_offense')
    op.drop_column('player_all_in_one_metrics', 'laker')
