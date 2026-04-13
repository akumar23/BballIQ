"""DARKO DPM historical data model.

Stores DARKO's Daily Plus-Minus history back to 1997 from nbarapm.com.
Includes box-score and on/off components of DPM.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DarkoHistory(Base):
    """Historical DARKO DPM data per player per season.

    Data from nbarapm.com /load/DARKO. 30 seasons, 1997-2026.
    """

    __tablename__ = "darko_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(100))
    season: Mapped[int] = mapped_column(Integer, index=True)
    team_name: Mapped[str | None] = mapped_column(String(50))
    age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))

    # Overall DPM
    dpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    o_dpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    d_dpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    dpm_rank: Mapped[int | None]
    o_dpm_rank: Mapped[int | None]
    d_dpm_rank: Mapped[int | None]

    # Box-score component
    box_odpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    box_ddpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # On/off component
    on_off_odpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    on_off_ddpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
