from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LineupStats(Base):
    """5-man lineup statistics for a season.

    Stores lineup composition, minutes, and ratings from LeagueDashLineups.
    Each row represents one unique 5-man combination.
    """

    __tablename__ = "lineup_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    season: Mapped[str] = mapped_column(String(10), index=True)
    team_id: Mapped[int | None] = mapped_column(BigInteger)
    team_abbreviation: Mapped[str | None] = mapped_column(String(10))

    # Lineup identity — sorted player IDs joined by "-"
    lineup_id: Mapped[str] = mapped_column(String(60), index=True)
    group_name: Mapped[str | None] = mapped_column(String(200))

    # Individual player foreign keys for efficient per-player queries
    player1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    player2_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    player3_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    player4_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)
    player5_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("players.id"), index=True)

    # Lineup stats
    games_played: Mapped[int | None] = mapped_column(Integer)
    minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    off_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    def_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
