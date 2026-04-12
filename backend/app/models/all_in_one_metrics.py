"""All-in-one impact metrics model.

Stores aggregated all-in-one player evaluation metrics from multiple
external sources: RAPM, RPM, EPM, RAPTOR, LEBRON, and DARKO.
Each metric includes overall, offensive, and defensive splits where available.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerAllInOneMetrics(Base):
    """All-in-one impact metrics for a player's season.

    Aggregates metrics from multiple sources:
    - RAPM: Self-computed via ridge regression on play-by-play data
    - RPM: ESPN's Real Plus-Minus (scraped)
    - EPM: Dunks & Threes Estimated Plus-Minus (scraped)
    - RAPTOR: FiveThirtyEight (historical only, discontinued)
    - LEBRON: BBall Index (scraped)
    - DARKO: The Athletic's DPM (CSV download)
    """

    __tablename__ = "player_all_in_one_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # RAPM (Regularized Adjusted Plus-Minus) — self-computed
    rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rapm_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rapm_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # RPM (Real Plus-Minus) — ESPN
    rpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rpm_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    rpm_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # EPM (Estimated Plus-Minus) — Dunks & Threes
    epm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    epm_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    epm_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # RAPTOR — FiveThirtyEight (historical/estimated)
    raptor: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raptor_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raptor_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # LEBRON — BBall Index
    lebron: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    lebron_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    lebron_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # DARKO DPM — The Athletic
    darko: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    darko_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    darko_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Source tracking — which sources were successfully fetched
    data_sources: Mapped[str | None] = mapped_column(
        Text, comment="Comma-separated list of sources that provided data"
    )

    player = relationship("Player", back_populates="all_in_one_metrics")
