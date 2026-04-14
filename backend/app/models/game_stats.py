"""Per-game box score stats for a player.

Populated from the PlayerGameLogs bulk endpoint. Each row represents
a single game played by a single player in a given season.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GameStats(Base):
    __tablename__ = "game_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    season: Mapped[str | None] = mapped_column(String(10), index=True)
    game_id: Mapped[str] = mapped_column(String(20), index=True)
    game_date: Mapped[str | None] = mapped_column(String(30))
    matchup: Mapped[str | None] = mapped_column(String(20))
    wl: Mapped[str | None] = mapped_column(String(1))

    # Box score
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    points: Mapped[int | None]
    assists: Mapped[int | None]
    rebounds: Mapped[int | None]
    offensive_rebounds: Mapped[int | None]
    defensive_rebounds: Mapped[int | None]
    steals: Mapped[int | None]
    blocks: Mapped[int | None]
    blocks_against: Mapped[int | None]
    turnovers: Mapped[int | None]
    personal_fouls: Mapped[int | None]
    fouls_drawn: Mapped[int | None]
    plus_minus: Mapped[int | None]

    # Shooting
    fgm: Mapped[int | None]
    fga: Mapped[int | None]
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    fg3m: Mapped[int | None]
    fg3a: Mapped[int | None]
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    ftm: Mapped[int | None]
    fta: Mapped[int | None]
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Milestones
    double_double: Mapped[int | None]
    triple_double: Mapped[int | None]

    # Fantasy
    fantasy_pts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Tracking - Offensive (populated separately if available)
    touches: Mapped[int | None]
    front_court_touches: Mapped[int | None]
    time_of_possession: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    avg_seconds_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    avg_dribbles_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    points_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    paint_touches: Mapped[int | None]
    post_touches: Mapped[int | None]
    elbow_touches: Mapped[int | None]

    # Tracking - Defensive (populated separately if available)
    deflections: Mapped[int | None]
    contested_shots_2pt: Mapped[int | None]
    contested_shots_3pt: Mapped[int | None]
    charges_drawn: Mapped[int | None]
    loose_balls_recovered: Mapped[int | None]

    # Calculated metrics
    offensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    defensive_metric: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    game_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    player = relationship("Player", back_populates="game_stats")
