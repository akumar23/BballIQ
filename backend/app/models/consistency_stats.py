"""Player consistency/variance metrics model.

Computed from game logs to measure how steady or volatile a player
performs game-to-game. Lower CV = more consistent.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerConsistencyStats(Base):
    """Consistency metrics derived from game-by-game data."""

    __tablename__ = "player_consistency_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    games_used: Mapped[int | None]  # Number of games in calculation

    # Coefficient of variation (std_dev / mean) — lower = more consistent
    pts_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    ast_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    reb_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    fantasy_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    game_score_cv: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    # Standard deviations (raw volatility)
    pts_std: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ast_std: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    reb_std: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    game_score_std: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Game Score stats (Hollinger formula)
    game_score_avg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    game_score_median: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    game_score_max: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    game_score_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Boom/bust analysis
    boom_games: Mapped[int | None]  # Games > mean + 1 std_dev (scoring)
    bust_games: Mapped[int | None]  # Games < mean - 1 std_dev (scoring)
    boom_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    bust_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Streaks
    best_streak: Mapped[int | None]  # Longest streak above mean
    worst_streak: Mapped[int | None]  # Longest streak below mean

    # Double-double / triple-double rates
    dd_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    td_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Overall consistency grade (0-100 percentile, computed vs league)
    consistency_score: Mapped[int | None]

    player = relationship("Player", back_populates="consistency_stats")
