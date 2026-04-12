"""Player matchup statistics model.

Stores player-vs-player defensive matchup data from the
LeagueSeasonMatchups endpoint, including per-matchup shooting stats,
possessions, and assist/turnover/block data.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerMatchups(Base):
    """Player-vs-player defensive matchup data for a season.

    Each row represents one defender vs one offensive player matchup
    across the season. Data from LeagueSeasonMatchups endpoint.
    """

    __tablename__ = "player_matchups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Offensive player being guarded
    off_player_nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    off_player_name: Mapped[str] = mapped_column(String(100))

    # Matchup volume
    games_played: Mapped[int | None] = mapped_column(Integer)
    matchup_min: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    partial_poss: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # Scoring
    player_pts: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    team_pts: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # Matchup shooting
    matchup_fgm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_fga: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    matchup_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    matchup_ftm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_fta: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # Playmaking / disruption
    matchup_ast: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_tov: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    matchup_blk: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sfl: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # Shooting fouls

    # Help defense
    help_blk: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    help_fgm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    help_fga: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    help_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="matchups")
