"""Player opponent shooting model.

Captures the shot distribution and efficiency that an individual defender
*allows* opponents to achieve, sourced from LeagueDashPtDefend with the
"2 Pointers" and "Greater Than 15Ft" defense categories — complements the
existing Overall / Less Than 6Ft / 3 Pointers coverage to give a complete
picture of shot defense by distance.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerOpponentShooting(Base):
    """Shooting allowed by a defender split by shot distance bucket."""

    __tablename__ = "player_opponent_shooting"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Defender context (populated from the 2PT row — widest sample)
    age: Mapped[int | None]
    player_position: Mapped[str | None] = mapped_column(String(10))
    two_pt_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    long_mid_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    lt_10ft_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Overall 2-point shots allowed ---
    two_pt_games: Mapped[int | None] = mapped_column(BigInteger)
    two_pt_defended_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    two_pt_defended_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    two_pt_defended_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    two_pt_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    two_pt_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Long midrange (>15 ft, 2-point) shots allowed ---
    long_mid_defended_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    long_mid_defended_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    long_mid_defended_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    long_mid_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    long_mid_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Less than 10 ft shots allowed (near-rim + short paint) ---
    lt_10ft_defended_fgm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    lt_10ft_defended_fga: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    lt_10ft_defended_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    lt_10ft_normal_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    lt_10ft_pct_plusminus: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="opponent_shooting")
