"""Player passing tracking model.

Per-game passing metrics from NBA tracking Passing endpoint.
Includes pass volume, assist quality, and adjusted assist metrics.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerPassingStats(Base):
    """Passing tracking stats for a player's season."""

    __tablename__ = "player_passing_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Pass volume (per game)
    passes_made: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    passes_received: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Assist tracking (per game)
    ft_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    secondary_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    potential_ast: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ast_points_created: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    ast_adj: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    # Assist efficiency (ratios)
    ast_to_pass_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    ast_to_pass_pct_adj: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))

    player = relationship("Player", back_populates="passing_stats")
