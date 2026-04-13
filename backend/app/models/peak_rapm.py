"""Peak RAPM leaderboard model.

Stores each player's best RAPM values across different rolling windows
and metrics from nbarapm.com's peak leaderboard.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PeakRapm(Base):
    """Peak RAPM data for a player across different window sizes.

    Each row represents a player's peak value for a specific dataset
    (e.g., "Peak 3Y RAPM", "Peak 5Y ORAPM"). Data from /api/peakleaderboard.
    """

    __tablename__ = "peak_rapm"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nba_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(100))
    dataset: Mapped[str] = mapped_column(String(30), index=True)

    orapm: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    drapm: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    rapm: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    orapm_rank: Mapped[int | None]
    drapm_rank: Mapped[int | None]
    rapm_rank: Mapped[int | None]

    current: Mapped[int | None]  # 1 = currently active player
    team_id: Mapped[int | None] = mapped_column(BigInteger)
