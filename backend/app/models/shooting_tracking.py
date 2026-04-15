"""Player shooting tracking model.

Stores per-game catch-and-shoot, pull-up, and drive tracking stats
for each player per season. Data sourced from the NBA tracking
endpoints (LeagueDashPtStats).
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerShootingTracking(Base):
    """Shooting tracking statistics for a player's season.

    Includes catch-and-shoot, pull-up shooting, and drive metrics.
    All values are per-game averages.
    """

    __tablename__ = "player_shooting_tracking"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Catch and Shoot (per game)
    catch_shoot_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    catch_shoot_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    catch_shoot_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    catch_shoot_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    catch_shoot_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    catch_shoot_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    catch_shoot_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    catch_shoot_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Pull Up (per game)
    pullup_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pullup_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pullup_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pullup_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pullup_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pullup_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    pullup_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    pullup_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # Drives (per game) — full set from LeagueDashPtStats pt_measure_type=Drives
    drives: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_ftm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_fta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_pts_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_passes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_passes_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_ast_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_tov: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    drive_pf: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    drive_pf_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="shooting_tracking")
