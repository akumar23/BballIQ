"""Computed advanced statistics model.

Stores derived advanced metrics for each player per season, including
PER, BPM, VORP, Win Shares, and radar chart percentiles. These are
calculated from raw box-score and tracking data rather than fetched
directly from an API.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerComputedAdvanced(Base):
    """Computed advanced statistics for a player's season.

    Includes PER, BPM components, Win Shares, and radar chart
    percentile values used for player profile visualizations.
    """

    __tablename__ = "player_computed_advanced"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # PER
    per: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # BPM components
    obpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dbpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    vorp: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Win Shares
    ows: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dws: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ws: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ws_per_48: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    # Radar percentiles (0-100)
    radar_scoring: Mapped[int | None] = mapped_column(Integer)
    radar_playmaking: Mapped[int | None] = mapped_column(Integer)
    radar_defense: Mapped[int | None] = mapped_column(Integer)
    radar_efficiency: Mapped[int | None] = mapped_column(Integer)
    radar_volume: Mapped[int | None] = mapped_column(Integer)
    radar_durability: Mapped[int | None] = mapped_column(Integer)
    radar_clutch: Mapped[int | None] = mapped_column(Integer)
    radar_versatility: Mapped[int | None] = mapped_column(Integer)

    player = relationship("Player", back_populates="computed_advanced")
