from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Per75Stats(Base):
    """Per 75 possessions stats for a player's season.

    These stats normalize player production to a standard 75 possessions,
    which roughly represents the number of possessions in a typical NBA game.
    This allows for fair comparison across players with different minutes loads.
    """

    __tablename__ = "per_75_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    season_stats_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("season_stats.id"), unique=True, index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)  # e.g., "2024-25"

    # Per 75 possessions - Scoring
    pts_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fgm_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fga_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg3m_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg3a_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ftm_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fta_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per 75 possessions - Playmaking
    ast_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    tov_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per 75 possessions - Rebounding
    reb_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    oreb_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dreb_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per 75 possessions - Defense
    stl_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    blk_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per 75 possessions - Hustle stats
    deflections_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    contested_shots_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    contested_2pt_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    contested_3pt_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    charges_drawn_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    loose_balls_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    box_outs_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    screen_assists_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Per 75 possessions - Touches/Ball handling
    touches_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    front_court_touches_per_75: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Possessions used for calculation (for reference)
    possessions_used: Mapped[int | None]

    season_stats = relationship("SeasonStats", back_populates="per_75_stats")
