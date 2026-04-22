"""Forced turnovers (rFTOV) model.

Stores relative forced turnover data from nbarapm.com.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ForcedTurnovers(Base):
    """Forced turnover metrics per player.

    rFTOV measures a player's impact on forcing defensive turnovers,
    relative to league average. Data from nbarapm.com /load/rFTOV.
    """

    __tablename__ = "forced_turnovers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(100))

    dtov: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    total_def_poss: Mapped[int | None]
    weighted_avg_rftov: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
