"""Player shooting by closest defender distance model.

Per-game shooting stats broken down by defender proximity:
- Very Tight (0-2 ft)
- Tight (2-4 ft)
- Open (4-6 ft)
- Wide Open (6+ ft)

Data from LeagueDashPlayerPtShot with close_def_dist_range filter. Captures
the full set of fields the endpoint returns: overall FGM/FGA/FG%/eFG%, the
2PT split (FG2M / FG2A / FG2%, plus frequency), and the 3PT split.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerDefenderDistanceShooting(Base):
    """Shooting stats by closest defender distance for a player's season."""

    __tablename__ = "player_defender_distance_shooting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # --- Very Tight (0-2 ft) ---
    very_tight_fga_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_fg2a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_fg2m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_fg3a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    very_tight_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    very_tight_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Tight (2-4 ft) ---
    tight_fga_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_fg2a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_fg2m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_fg3a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    tight_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tight_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Open (4-6 ft) ---
    open_fga_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_fg2a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_fg2m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_fg3a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    open_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    open_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Wide Open (6+ ft) ---
    wide_open_fga_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_fg2a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_fg2m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_fg3a_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    wide_open_fg3m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    wide_open_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="defender_distance_shooting")
