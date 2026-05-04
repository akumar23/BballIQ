"""Team-shooting on/off splits for a player.

Captures how the team's shot diet and efficiency change between when the
player is on vs. off the court. Sourced from the NBA stats endpoint
``TeamPlayerOnOffSummary`` with ``measure_type_detailed_defense="Shooting"``.

These splits are the primary input to the new gravity index's
``teammate_lift`` component: a high-gravity off-ball shooter pulls
defenders away from teammates, lifting team eFG% and the share of open /
wide-open three attempts when on the floor.

Schema is keyed ``(player_id, season)`` to mirror ``PlayerOnOffStats`` and
slot into the same upsert pattern used by the impact-data refresh task.
"""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PlayerOnOffShooting(Base):
    """Team shooting splits when a player is on vs. off the court.

    All values are at the team level (not the focal player's own shots).
    Differentials are stored as ``on - off``; positive means the team
    shoots better / takes more wide-open looks when the player is on.
    """

    __tablename__ = "player_on_off_shooting"
    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", name="uq_player_on_off_shooting_player_season"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Sample-size signals — used by the Bayesian shrinkage prior.
    on_court_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    off_court_minutes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    # --- Effective FG% (team) ---
    on_court_team_efg: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_court_team_efg: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    team_efg_diff: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Open 3PA frequency (team) ---
    on_court_team_open3_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_court_team_open3_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    team_open3_freq_diff: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Wide-open 3PA frequency (team) ---
    on_court_team_wide_open3_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_court_team_wide_open3_freq: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    team_wide_open3_freq_diff: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Catch-and-shoot share of team FGA ---
    on_court_team_catch_shoot_share: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 3)
    )
    off_court_team_catch_shoot_share: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 3)
    )
    team_catch_shoot_share_diff: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    # --- Pull-up share of team FGA (kept for completeness; cheap to store) ---
    on_court_team_pullup_share: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    off_court_team_pullup_share: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    team_pullup_share_diff: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))

    player = relationship("Player", back_populates="on_off_shooting")
