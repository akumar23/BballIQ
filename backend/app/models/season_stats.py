from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SeasonStats(Base):
    __tablename__ = "season_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    season: Mapped[str] = mapped_column(String(10), index=True)  # e.g., "2024-25"

    # Game info
    games_played: Mapped[int | None]
    total_minutes: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))

    # Traditional box score totals
    total_points: Mapped[int | None]
    total_assists: Mapped[int | None]
    total_rebounds: Mapped[int | None]
    total_offensive_rebounds: Mapped[int | None]
    total_defensive_rebounds: Mapped[int | None]
    total_steals: Mapped[int | None]
    total_blocks: Mapped[int | None]
    total_turnovers: Mapped[int | None]
    total_fgm: Mapped[int | None]
    total_fga: Mapped[int | None]
    total_fg3m: Mapped[int | None]
    total_fg3a: Mapped[int | None]
    total_ftm: Mapped[int | None]
    total_fta: Mapped[int | None]
    total_plus_minus: Mapped[int | None]

    # Aggregated tracking - Offensive
    total_touches: Mapped[int | None]
    total_front_court_touches: Mapped[int | None]
    total_time_of_possession: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    avg_points_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Aggregated tracking - Hustle/Defensive
    total_deflections: Mapped[int | None]
    total_contested_shots: Mapped[int | None]
    total_contested_shots_2pt: Mapped[int | None]
    total_contested_shots_3pt: Mapped[int | None]
    total_charges_drawn: Mapped[int | None]
    total_loose_balls_recovered: Mapped[int | None]
    total_box_outs: Mapped[int | None]
    total_box_outs_off: Mapped[int | None]
    total_box_outs_def: Mapped[int | None]
    total_screen_assists: Mapped[int | None]
    total_screen_assist_pts: Mapped[int | None]

    # Estimated possessions (for per-possession calculations)
    estimated_possessions: Mapped[int | None]

    # Calculated metrics (season averages)
    offensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    defensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    overall_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # League percentiles
    offensive_percentile: Mapped[int | None]
    defensive_percentile: Mapped[int | None]

    player = relationship("Player", back_populates="season_stats")
    per_75_stats = relationship("Per75Stats", back_populates="season_stats", uselist=False)
