"""Multi-year RAPM window model.

Stores pure Regularized Adjusted Plus-Minus across multiple time windows
(2-year, 3-year, 4-year, 5-year, and timedecay) from nbarapm.com.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerRapmWindows(Base):
    """Multi-year RAPM windows for a player.

    Each row stores a player's RAPM values across all rolling windows
    for the current period. Data sourced from nbarapm.com /load/current_comp.
    """

    __tablename__ = "player_rapm_windows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Timedecay RAPM (recency-weighted)
    timedecay_orapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    timedecay_drapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    timedecay_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    timedecay_orapm_rank: Mapped[int | None]
    timedecay_drapm_rank: Mapped[int | None]
    timedecay_rapm_rank: Mapped[int | None]

    # 2-year rolling RAPM
    two_year_orapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    two_year_drapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    two_year_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    two_year_orapm_rank: Mapped[int | None]
    two_year_drapm_rank: Mapped[int | None]
    two_year_rapm_rank: Mapped[int | None]

    # 3-year rolling RAPM
    three_year_orapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_year_drapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_year_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    three_year_orapm_rank: Mapped[int | None]
    three_year_drapm_rank: Mapped[int | None]
    three_year_rapm_rank: Mapped[int | None]

    # 4-year rolling RAPM
    four_year_orapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    four_year_drapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    four_year_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    four_year_orapm_rank: Mapped[int | None]
    four_year_drapm_rank: Mapped[int | None]
    four_year_rapm_rank: Mapped[int | None]

    # 5-year rolling RAPM
    five_year_orapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    five_year_drapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    five_year_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    five_year_orapm_rank: Mapped[int | None]
    five_year_drapm_rank: Mapped[int | None]
    five_year_rapm_rank: Mapped[int | None]

    player = relationship("Player", back_populates="rapm_windows")
