"""Player touches breakdown model.

Per-game tracking metrics from NBA LeagueDashPtStats with ElbowTouch, PostTouch,
and PaintTouch measure types. Captures frequency, efficiency, passing, turnovers,
and fouls on each touch type — useful for understanding offensive role and
efficiency in specific spots on the floor.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerTouchesBreakdown(Base):
    """Elbow/post/paint touches breakdown for a player's season."""

    __tablename__ = "player_touches_breakdown"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # --- Elbow touches ---
    elbow_touches: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    elbow_touch_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    elbow_touch_ftm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_fta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    elbow_touch_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_passes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_tov: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_fouls: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    elbow_touch_pts_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Post touches ---
    post_touches: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    post_touch_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_touch_ftm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_fta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    post_touch_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_passes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_tov: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_fouls: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    post_touch_pts_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Paint touches ---
    paint_touches: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    paint_touch_fgm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_fga: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    paint_touch_ftm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_fta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    paint_touch_pts: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_passes: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_tov: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_fouls: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    paint_touch_pts_per_touch: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="touches_breakdown")
