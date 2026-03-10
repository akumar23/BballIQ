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
