"""Player advanced statistics model.

Stores per-game advanced stats for each player per season, including
efficiency metrics (TS%, EFG%), usage rate, offensive/defensive ratings,
pace, and various percentage-based advanced metrics.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerAdvancedStats(Base):
    """Advanced statistics for a player's season.

    Includes shooting efficiency, usage, ratings, pace, and
    percentage-based metrics from the NBA Advanced stats endpoint.
    """

    __tablename__ = "player_advanced_stats"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", name="uq_player_advanced_stats_player_season"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Shooting efficiency
    ts_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Usage and involvement
    usg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Ratings
    off_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    def_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))

    # Pace and overall efficiency
    pace: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pie: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Assist metrics
    ast_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    ast_to: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ast_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    # Rebounding percentages
    oreb_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    dreb_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    reb_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Turnover percentage
    tm_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    # Estimated variants (from NBA's "Advanced" measure type)
    e_off_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    e_def_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    e_net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    e_usg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    e_pace: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    pace_per40: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Possessions (raw) — foundation for per-possession normalization
    poss: Mapped[int | None]

    player = relationship("Player", back_populates="advanced_stats")
