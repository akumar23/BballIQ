from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(20))
    team_id: Mapped[int | None] = mapped_column(BigInteger)
    team_abbreviation: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Bio data
    height: Mapped[str | None] = mapped_column(String(10))  # e.g. "6-6"
    height_inches: Mapped[int | None] = mapped_column(BigInteger)
    weight: Mapped[int | None] = mapped_column(BigInteger)  # lbs
    jersey_number: Mapped[str | None] = mapped_column(String(5))
    birth_date: Mapped[str | None] = mapped_column(String(20))  # ISO date string
    country: Mapped[str | None] = mapped_column(String(50))
    college: Mapped[str | None] = mapped_column(String(120))
    draft_year: Mapped[int | None] = mapped_column(BigInteger)
    draft_round: Mapped[int | None] = mapped_column(BigInteger)
    draft_number: Mapped[int | None] = mapped_column(BigInteger)

    game_stats = relationship("GameStats", back_populates="player")
    season_stats = relationship("SeasonStats", back_populates="player")
    on_off_stats = relationship("PlayerOnOffStats", back_populates="player")
    contextualized_impact = relationship("ContextualizedImpact", back_populates="player")
    game_play_type_stats = relationship("GamePlayTypeStats", back_populates="player")
    season_play_type_stats = relationship("SeasonPlayTypeStats", back_populates="player")
    advanced_stats = relationship("PlayerAdvancedStats", back_populates="player")
    shot_zones = relationship("PlayerShotZones", back_populates="player")
    clutch_stats = relationship("PlayerClutchStats", back_populates="player")
    defensive_stats = relationship("PlayerDefensiveStats", back_populates="player")
    computed_advanced = relationship("PlayerComputedAdvanced", back_populates="player")
    career_stats = relationship("PlayerCareerStats", back_populates="player")
    shooting_tracking = relationship("PlayerShootingTracking", back_populates="player")
    matchups = relationship("PlayerMatchups", back_populates="player")
    all_in_one_metrics = relationship("PlayerAllInOneMetrics", back_populates="player")
    rapm_windows = relationship("PlayerRapmWindows", back_populates="player")
    big_board = relationship("PlayerBigBoard", back_populates="player")
    speed_distance = relationship("PlayerSpeedDistance", back_populates="player")
    passing_stats = relationship("PlayerPassingStats", back_populates="player")
    rebounding_tracking = relationship("PlayerReboundingTracking", back_populates="player")
    defender_distance_shooting = relationship("PlayerDefenderDistanceShooting", back_populates="player")
    defensive_play_types = relationship("PlayerDefensivePlayTypes", back_populates="player")
    consistency_stats = relationship("PlayerConsistencyStats", back_populates="player")
    touches_breakdown = relationship("PlayerTouchesBreakdown", back_populates="player")
    opponent_shooting = relationship("PlayerOpponentShooting", back_populates="player")
