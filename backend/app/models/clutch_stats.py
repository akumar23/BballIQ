"""Player clutch statistics model.

Stores per-game clutch time stats for each player per season.
Clutch time is defined as the last 5 minutes of a game when the
score differential is 5 points or fewer.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerClutchStats(Base):
    """Clutch time statistics for a player's season.

    All shooting and counting stats are per-game averages during
    clutch situations (last 5 minutes, within 5 points).
    """

    __tablename__ = "player_clutch_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", name="uq_player_clutch_stats_player_season"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Game info
    games_played: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per-game scoring
    pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Field goals
    fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Three-pointers
    fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Free throws
    ftm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Counting stats (per game)
    ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    stl: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    blk: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tov: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Impact
    plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))

    player = relationship("Player", back_populates="clutch_stats")
