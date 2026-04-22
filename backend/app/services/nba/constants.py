"""Play-type name mappings used by the offensive/defensive synergy fetchers."""

from __future__ import annotations

# Play type name mappings for NBA API
PLAY_TYPE_MAPPING = {
    "isolation": "Isolation",
    "pnr_ball_handler": "PRBallHandler",
    "pnr_roll_man": "PRRollman",
    "post_up": "Postup",
    "spot_up": "Spotup",
    "transition": "Transition",
    "cut": "Cut",
    "off_screen": "OffScreen",
    "handoff": "Handoff",
}

# Key defensive play types for defensive synergy data
DEFENSIVE_PLAY_TYPE_MAPPING = {
    "isolation": "Isolation",
    "pnr_ball_handler": "PRBallHandler",
    "post_up": "Postup",
    "spot_up": "Spotup",
    "transition": "Transition",
}
