from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GameStats(Base):
    __tablename__ = "game_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    game_id: Mapped[int] = mapped_column(BigInteger, index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)

    # Basic stats
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    points: Mapped[int | None]
    assists: Mapped[int | None]
    rebounds: Mapped[int | None]
    steals: Mapped[int | None]
    blocks: Mapped[int | None]
    turnovers: Mapped[int | None]

    # Tracking - Offensive
    touches: Mapped[int | None]
    front_court_touches: Mapped[int | None]
    time_of_possession: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    avg_seconds_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    avg_dribbles_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    points_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    paint_touches: Mapped[int | None]
    post_touches: Mapped[int | None]
    elbow_touches: Mapped[int | None]

    # Tracking - Defensive
    deflections: Mapped[int | None]
    contested_shots_2pt: Mapped[int | None]
    contested_shots_3pt: Mapped[int | None]
    charges_drawn: Mapped[int | None]
    loose_balls_recovered: Mapped[int | None]

    # Calculated metrics
    offensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    defensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    player = relationship("Player", back_populates="game_stats")
