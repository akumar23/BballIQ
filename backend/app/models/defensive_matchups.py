"""Player defensive statistics model.

Stores comprehensive defensive stats for each player per season, including
overall defensive FG%, rim protection, 3-point defense, and isolation
defense from synergy play type data.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerDefensiveStats(Base):
    """Comprehensive defensive statistics for a player's season.

    Combines data from multiple defensive endpoints:
    - Overall defensive FG% (LeagueDashPtDefend Overall)
    - Rim protection (LeagueDashPtDefend Less Than 6Ft)
    - 3-point defense (LeagueDashPtDefend 3 Pointers)
    - Isolation defense (SynergyPlayTypes defensive)
    """

    __tablename__ = "player_defensive_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", name="uq_player_defensive_stats_player_season"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Defender context (games played + age). LeagueDashPtDefend returns
    # GP/G/FREQ per bucket — FREQ tells you how often this defender is the
    # closest defender on that shot type, which is essential for separating
    # "rarely at the rim" from "great at the rim."
    games_played: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[int | None] = mapped_column(Integer)

    # Overall defensive FG% stats
    overall_d_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    overall_d_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    overall_d_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    overall_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    overall_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    overall_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Rim protection (Less Than 6Ft)
    rim_d_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_d_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rim_d_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    rim_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    rim_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    rim_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # 3-point defense
    three_pt_d_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_pt_d_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_pt_d_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    three_pt_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    three_pt_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    three_pt_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Isolation defense (from synergy play types)
    iso_poss: Mapped[int | None] = mapped_column(Integer)
    iso_pts: Mapped[int | None] = mapped_column(Integer)
    iso_fgm: Mapped[int | None] = mapped_column(Integer)
    iso_fga: Mapped[int | None] = mapped_column(Integer)
    iso_ppp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    iso_percentile: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="defensive_stats")
