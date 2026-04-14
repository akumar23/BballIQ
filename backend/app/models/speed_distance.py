"""Player speed & distance tracking model.

Per-game averages from NBA tracking SpeedDistance endpoint.
Includes total distance, offensive/defensive splits, and average speeds.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerSpeedDistance(Base):
    """Speed and distance tracking stats for a player's season."""

    __tablename__ = "player_speed_distance"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Distance (per game, in miles)
    dist_miles: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dist_miles_off: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dist_miles_def: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Speed (mph)
    avg_speed: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    avg_speed_off: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    avg_speed_def: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Distance in feet (per game) for finer granularity
    dist_feet: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    player = relationship("Player", back_populates="speed_distance")
