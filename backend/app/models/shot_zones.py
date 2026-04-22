"""Player shot zone statistics model.

Stores per-game shot zone distribution for each player per season.
Each row represents one zone for one player, allowing flexible zone
names from the NBA API (Restricted Area, In The Paint, Mid-Range,
Left Corner 3, Right Corner 3, Above the Break 3, etc.).
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerShotZones(Base):
    """Shot zone statistics for a player's season.

    One row per player per zone per season, allowing flexible
    zone definitions from the NBA API.
    """

    __tablename__ = "player_shot_zones"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "season",
            "zone",
            name="uq_player_shot_zones_player_season_zone",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Zone identification
    zone: Mapped[str] = mapped_column(String(50))

    # Player stats for this zone
    fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # League average FG% for this zone (for comparison)
    league_avg: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="shot_zones")
