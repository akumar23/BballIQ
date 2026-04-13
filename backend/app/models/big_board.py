"""Player Big Board model.

Comprehensive per-player analytics from nbarapm.com's Big Board export,
including shooting, passing, defense, play types, and offensive archetypes.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerBigBoard(Base):
    """Comprehensive per-player analytics from nbarapm.com Big Board.

    Contains 70+ metrics covering shooting efficiency, passing, defense,
    play type impact, and offensive archetypes. Data from /load/player_stats_export.
    """

    __tablename__ = "player_big_board"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Bio / context
    position: Mapped[str | None] = mapped_column(String(10))
    offensive_archetype: Mapped[str | None] = mapped_column(String(50))
    age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    games_played: Mapped[int | None]
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    mpg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    # Scoring efficiency
    pts_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ts_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ts_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    relative_ts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    relative_ts_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    mod_ts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ts_added_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ts_added_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    tsa_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    tsa_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    # Shooting splits
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg2_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    fg2a_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg3_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    fg3a_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_point_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ft_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    fta_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ftr: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ftr_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    # Catch-and-shoot / pull-up 3PT
    cs_3pa: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    cs_3pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pu_3pa: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pu_3pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Passing
    assists_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    assists_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    potential_assists_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    at_rim_assists_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    mid_assists_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_pt_assists_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    assist_efg: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    assist_efg_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    on_ball_time_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    on_ball_time_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    bad_pass_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    bad_pass_tov_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Turnovers
    scoring_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    scoring_tov_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    scoring_tovs_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Defense
    dfga_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dfga_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    dif_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dif_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    stops_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    stops_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    relative_stops_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    blocks_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    steals_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    offd_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    points_saved_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    points_saved_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    forced_tov_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    forced_tov_per_100_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    # Rim defense
    rim_dfga_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_dif_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_dif_pct_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    rim_points_saved_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_freq_on: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_freq_onoff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_acc_on: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_acc_onoff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Rebounding
    prob_off_rebounded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    self_oreb_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    teammate_miss_oreb_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Play type impact
    playtype_rppp: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    playtype_rppp_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    playtype_ts_rppp: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    playtype_tov_rppp: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    playtype_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    playtype_diff_percentile: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    playtype_adj_rppp: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    pt_adj_rts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Shooting context
    first_chance_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    second_fg_created_per_100: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    player = relationship("Player", back_populates="big_board")
