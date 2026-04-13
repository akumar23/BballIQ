"""RAPTOR historical data model.

Stores FiveThirtyEight's RAPTOR metric history back to 1977.
FiveThirtyEight discontinued RAPTOR; this is a preserved archive from nbarapm.com.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RaptorHistory(Base):
    """Historical RAPTOR data per player per season.

    Data from nbarapm.com /load/raptor. Uses Basketball Reference player IDs
    (not NBA.com IDs) for historical players.
    """

    __tablename__ = "raptor_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_name: Mapped[str] = mapped_column(String(100), index=True)
    nba_id: Mapped[str] = mapped_column(String(20), index=True)  # BBRef ID for historical
    season: Mapped[int] = mapped_column(Integer, index=True)

    minutes: Mapped[int | None]
    possessions: Mapped[int | None]

    raptor_offense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raptor_defense: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    raptor_total: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    war_total: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    o_raptor_rank: Mapped[int | None]
    d_raptor_rank: Mapped[int | None]
    raptor_rank: Mapped[int | None]
