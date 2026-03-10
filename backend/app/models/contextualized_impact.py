from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ContextualizedImpact(Base):
    """Contextualized impact rating for a player's season.

    This metric adjusts raw on/off data by accounting for:
    - Teammate quality (playing with stars inflates stats)
    - Opponent quality (playing against starters vs bench)
    - Minutes context (more minutes = more reliable)

    Formula:
        contextualized_impact = raw_net_rating_diff
            - teammate_adjustment (avg teammate net rating - league avg)
            * opponent_quality_factor (weighted by minutes vs starters/bench)
            * reliability_factor (based on total minutes)
    """

    __tablename__ = "contextualized_impact"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Raw on/off differential (baseline)
    raw_net_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raw_off_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raw_def_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Teammate context
    avg_teammate_net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    teammate_adjustment: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Opponent quality context
    pct_minutes_vs_starters: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    opponent_quality_factor: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Reliability context
    total_on_court_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    reliability_factor: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Final contextualized metrics
    contextualized_off_impact: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    contextualized_def_impact: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    contextualized_net_impact: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Percentile rankings
    impact_percentile: Mapped[int | None]
    offensive_impact_percentile: Mapped[int | None]
    defensive_impact_percentile: Mapped[int | None]

    player = relationship("Player", back_populates="contextualized_impact")
