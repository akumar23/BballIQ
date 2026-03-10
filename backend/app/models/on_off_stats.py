from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerOnOffStats(Base):
    """On/Off court statistics for a player's season.

    Tracks team performance when player is on vs off the court,
    providing raw differential data for impact calculations.
    """

    __tablename__ = "player_on_off_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # On-court stats
    on_court_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    on_court_plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    on_court_off_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    on_court_def_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    on_court_net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Off-court stats
    off_court_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    off_court_plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    off_court_off_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    off_court_def_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    off_court_net_rating: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Differentials (on - off)
    plus_minus_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    off_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    def_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    net_rating_diff: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    player = relationship("Player", back_populates="on_off_stats")
