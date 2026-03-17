"""Player career statistics model.

Stores career trajectory data with one row per player per historical
season. Used to render career progression charts and trajectory
analysis on the player card page.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerCareerStats(Base):
    """Career stats for a single season in a player's history.

    All counting stats are per-game averages as returned by the
    PlayerCareerStats endpoint with per_mode36="PerGame".
    """

    __tablename__ = "player_career_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Basic stats (per game)
    games_played: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    ppg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    rpg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    apg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    spg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    bpg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    # Shooting
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Team
    team_abbreviation: Mapped[str | None] = mapped_column(String(10))

    player = relationship("Player", back_populates="career_stats")
