from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SeasonStats(Base):
    __tablename__ = "season_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    season: Mapped[str] = mapped_column(String(10), index=True)  # e.g., "2024-25"

    # Aggregated stats
    games_played: Mapped[int | None]
    total_minutes: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    total_points: Mapped[int | None]
    total_assists: Mapped[int | None]
    total_rebounds: Mapped[int | None]

    # Aggregated tracking - Offensive
    total_touches: Mapped[int | None]
    total_front_court_touches: Mapped[int | None]
    total_time_of_possession: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    avg_points_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Aggregated tracking - Defensive
    total_deflections: Mapped[int | None]
    total_contested_shots: Mapped[int | None]
    total_charges_drawn: Mapped[int | None]
    total_loose_balls_recovered: Mapped[int | None]

    # Calculated metrics (season averages)
    offensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    defensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    overall_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # League percentiles
    offensive_percentile: Mapped[int | None]
    defensive_percentile: Mapped[int | None]

    player = relationship("Player", back_populates="season_stats")
