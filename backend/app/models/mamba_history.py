"""MAMBA historical data model.

Stores Timothy Wijaya's MAMBA hybrid impact metric history from nbarapm.com.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MambaHistory(Base):
    """Historical MAMBA metric data per player per season.

    Data from nbarapm.com /load/mamba.
    """

    __tablename__ = "mamba_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer, index=True)

    minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))

    o_mamba: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    d_mamba: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    mamba: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    o_mamba_rank: Mapped[int | None]
    d_mamba_rank: Mapped[int | None]
    mamba_rank: Mapped[int | None]
