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
