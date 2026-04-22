"""Game-level play type statistics model.

Stores per-game offensive play type stats for each player, including:
- Isolation
- Pick and Roll (Ball Handler)
- Pick and Roll (Roll Man)
- Post-up
- Spot-up
- Transition
- Cut
- Off-screen
"""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GamePlayTypeStats(Base):
    """Per-game play type statistics for a player.

    Each play type tracks:
    - Possessions (number of times player used this play type)
    - Points scored
    - Field goals made/attempted
    - For spot-up: 3-point makes/attempts
    """

    __tablename__ = "game_play_type_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id"), index=True
    )
    game_id: Mapped[str] = mapped_column(String(20), index=True)
    game_date: Mapped[date] = mapped_column(Date, index=True)
    season: Mapped[str] = mapped_column(String(10), index=True)

    # Isolation
    isolation_poss: Mapped[int | None]
    isolation_pts: Mapped[int | None]
    isolation_fgm: Mapped[int | None]
    isolation_fga: Mapped[int | None]

    # Pick and Roll - Ball Handler
    pnr_ball_handler_poss: Mapped[int | None]
    pnr_ball_handler_pts: Mapped[int | None]
    pnr_ball_handler_fgm: Mapped[int | None]
    pnr_ball_handler_fga: Mapped[int | None]

    # Pick and Roll - Roll Man
    pnr_roll_man_poss: Mapped[int | None]
    pnr_roll_man_pts: Mapped[int | None]
    pnr_roll_man_fgm: Mapped[int | None]
    pnr_roll_man_fga: Mapped[int | None]

    # Post-up
    post_up_poss: Mapped[int | None]
    post_up_pts: Mapped[int | None]
    post_up_fgm: Mapped[int | None]
    post_up_fga: Mapped[int | None]

    # Spot-up (includes 3-point tracking)
    spot_up_poss: Mapped[int | None]
    spot_up_pts: Mapped[int | None]
    spot_up_fgm: Mapped[int | None]
    spot_up_fga: Mapped[int | None]
    spot_up_fg3m: Mapped[int | None]
    spot_up_fg3a: Mapped[int | None]

    # Transition
    transition_poss: Mapped[int | None]
    transition_pts: Mapped[int | None]
    transition_fgm: Mapped[int | None]
    transition_fga: Mapped[int | None]

    # Cut
    cut_poss: Mapped[int | None]
    cut_pts: Mapped[int | None]
    cut_fgm: Mapped[int | None]
    cut_fga: Mapped[int | None]

    # Off-screen
    off_screen_poss: Mapped[int | None]
    off_screen_pts: Mapped[int | None]
    off_screen_fgm: Mapped[int | None]
    off_screen_fga: Mapped[int | None]

    # Total possessions for frequency calculation
    total_poss: Mapped[int | None]

    player = relationship("Player", back_populates="game_play_type_stats")
