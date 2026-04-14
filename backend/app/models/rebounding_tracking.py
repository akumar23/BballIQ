"""Player rebounding tracking model.

Per-game rebounding metrics from NBA tracking Rebounding endpoint.
Includes contested/uncontested splits, rebound chances, and distance.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerReboundingTracking(Base):
    """Rebounding tracking stats for a player's season."""

    __tablename__ = "player_rebounding_tracking"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Offensive rebounds (per game)
    oreb: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    oreb_contest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    oreb_uncontest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    oreb_contest_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    oreb_chances: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    oreb_chance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    oreb_chance_defer: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    oreb_chance_pct_adj: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    avg_oreb_dist: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Defensive rebounds (per game)
    dreb: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dreb_contest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dreb_uncontest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dreb_contest_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    dreb_chances: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dreb_chance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    dreb_chance_defer: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    dreb_chance_pct_adj: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    avg_dreb_dist: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Total rebounds (per game)
    reb: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb_contest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb_uncontest: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb_contest_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    reb_chances: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb_chance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    reb_chance_defer: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    reb_chance_pct_adj: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    avg_reb_dist: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    player = relationship("Player", back_populates="rebounding_tracking")
