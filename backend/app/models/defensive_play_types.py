"""Player defensive play type stats model.

Stores defensive Synergy play type data for each player per season.
Covers how effectively a player defends specific play types:
- Isolation
- Pick and Roll Ball Handler
- Post-up
- Spot-up
- Transition
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerDefensivePlayTypes(Base):
    """Defensive play type stats for a player's season."""

    __tablename__ = "player_defensive_play_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Total defensive possessions across tracked play types
    total_poss: Mapped[int | None]

    # Isolation defense
    iso_poss: Mapped[int | None]
    iso_pts: Mapped[int | None]
    iso_fgm: Mapped[int | None]
    iso_fga: Mapped[int | None]
    iso_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Pick and Roll Ball Handler defense
    pnr_ball_handler_poss: Mapped[int | None]
    pnr_ball_handler_pts: Mapped[int | None]
    pnr_ball_handler_fgm: Mapped[int | None]
    pnr_ball_handler_fga: Mapped[int | None]
    pnr_ball_handler_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pnr_ball_handler_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Post-up defense
    post_up_poss: Mapped[int | None]
    post_up_pts: Mapped[int | None]
    post_up_fgm: Mapped[int | None]
    post_up_fga: Mapped[int | None]
    post_up_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_up_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Spot-up defense
    spot_up_poss: Mapped[int | None]
    spot_up_pts: Mapped[int | None]
    spot_up_fgm: Mapped[int | None]
    spot_up_fga: Mapped[int | None]
    spot_up_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    spot_up_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Transition defense
    transition_poss: Mapped[int | None]
    transition_pts: Mapped[int | None]
    transition_fgm: Mapped[int | None]
    transition_fga: Mapped[int | None]
    transition_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    transition_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="defensive_play_types")
