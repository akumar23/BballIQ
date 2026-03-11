"""Season-aggregated play type statistics model.

Stores aggregated play type stats for each player per season, including
calculated metrics like PPP (points per possession), FG%, and frequency.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SeasonPlayTypeStats(Base):
    """Season-aggregated play type statistics for a player.

    Each play type includes:
    - Total possessions and points
    - PPP (points per possession)
    - FG% (field goal percentage)
    - Frequency (% of total possessions)
    - PPP percentile (ranking vs league)
    """

    __tablename__ = "season_play_type_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Total possessions across all play types (for frequency calculation)
    total_poss: Mapped[int | None]

    # Isolation
    isolation_poss: Mapped[int | None]
    isolation_pts: Mapped[int | None]
    isolation_fgm: Mapped[int | None]
    isolation_fga: Mapped[int | None]
    isolation_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    isolation_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    isolation_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    isolation_ppp_percentile: Mapped[int | None]

    # Pick and Roll - Ball Handler
    pnr_ball_handler_poss: Mapped[int | None]
    pnr_ball_handler_pts: Mapped[int | None]
    pnr_ball_handler_fgm: Mapped[int | None]
    pnr_ball_handler_fga: Mapped[int | None]
    pnr_ball_handler_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_ppp_percentile: Mapped[int | None]

    # Pick and Roll - Roll Man
    pnr_roll_man_poss: Mapped[int | None]
    pnr_roll_man_pts: Mapped[int | None]
    pnr_roll_man_fgm: Mapped[int | None]
    pnr_roll_man_fga: Mapped[int | None]
    pnr_roll_man_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_roll_man_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_roll_man_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_roll_man_ppp_percentile: Mapped[int | None]

    # Post-up
    post_up_poss: Mapped[int | None]
    post_up_pts: Mapped[int | None]
    post_up_fgm: Mapped[int | None]
    post_up_fga: Mapped[int | None]
    post_up_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_ppp_percentile: Mapped[int | None]

    # Spot-up (includes 3-point tracking)
    spot_up_poss: Mapped[int | None]
    spot_up_pts: Mapped[int | None]
    spot_up_fgm: Mapped[int | None]
    spot_up_fga: Mapped[int | None]
    spot_up_fg3m: Mapped[int | None]
    spot_up_fg3a: Mapped[int | None]
    spot_up_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_ppp_percentile: Mapped[int | None]

    # Transition
    transition_poss: Mapped[int | None]
    transition_pts: Mapped[int | None]
    transition_fgm: Mapped[int | None]
    transition_fga: Mapped[int | None]
    transition_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_ppp_percentile: Mapped[int | None]

    # Cut
    cut_poss: Mapped[int | None]
    cut_pts: Mapped[int | None]
    cut_fgm: Mapped[int | None]
    cut_fga: Mapped[int | None]
    cut_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    cut_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    cut_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    cut_ppp_percentile: Mapped[int | None]

    # Off-screen
    off_screen_poss: Mapped[int | None]
    off_screen_pts: Mapped[int | None]
    off_screen_fgm: Mapped[int | None]
    off_screen_fga: Mapped[int | None]
    off_screen_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_screen_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_screen_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_screen_ppp_percentile: Mapped[int | None]

    player = relationship("Player", back_populates="season_play_type_stats")
