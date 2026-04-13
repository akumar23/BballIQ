"""Six Factor RAPM model.

Stores RAPM decomposed into six factors (eFG, TOV, OREB, FTR) on both
offense and defense, from nbarapm.com's scaled factor RAPM data.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SixFactorRapm(Base):
    """Six Factor RAPM decomposition for a player over a time window.

    Breaks down RAPM into why a player helps/hurts: shooting efficiency,
    turnovers, offensive rebounding, and free throw rate on both ends.
    Data from nbarapm.com /load/SCALEDOUTPUT_SMALLER.
    """

    __tablename__ = "six_factor_rapm"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(100))
    year_interval: Mapped[str] = mapped_column(String(5), index=True)  # 2Y, 3Y, 4Y, 5Y
    latest_year: Mapped[int]

    # Possessions
    off_poss: Mapped[int | None]

    # Overall RAPM
    off_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    def_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ovr_rapm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    off_rapm_rank: Mapped[int | None]
    def_rapm_rank: Mapped[int | None]
    ovr_rapm_rank: Mapped[int | None]

    # Offensive factors (scaled contribution to off RAPM)
    sc_off_ts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_off_ts_rank: Mapped[int | None]
    sc_off_tov: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_off_tov_rank: Mapped[int | None]
    sc_off_reb: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_off_reb_rank: Mapped[int | None]

    # Defensive factors (scaled contribution to def RAPM)
    sc_def_ts: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_def_ts_rank: Mapped[int | None]
    sc_def_tov: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_def_tov_rank: Mapped[int | None]
    sc_def_reb: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_def_reb_rank: Mapped[int | None]

    # Possession factor
    sc_poss: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    sc_poss_rank: Mapped[int | None]

    # Residuals (diff between raw and factor sum)
    off_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    def_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
