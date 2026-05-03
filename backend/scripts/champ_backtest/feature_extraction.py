"""Build ChampionshipCalculator inputs from historical scrape outputs.

The production calculator (``app.services.championship.ChampionshipCalculator``)
expects SQLAlchemy model instances. Rather than instantiate ORM objects we
construct ``types.SimpleNamespace`` shims whose attribute names match the
model fields the calculator actually reads. The relevant fields are
documented below in :data:`SEASON_STATS_FIELDS` etc.

For seasons before play-type tracking (pre-2015) or clutch-stats reporting
(pre-2018) the corresponding inputs are returned as ``None`` so the
calculator's documented graceful-fallback paths kick in.

Portability is fixed at ``50.0`` (neutral) for the backtest -- computing
historical portability is out of scope. Teammate impact uses the top-4
non-target-player BPMs from the same team-season.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# Attribute names actually accessed on each input by ChampionshipCalculator.
# Sourced by grepping ``self.<alias>.<field>`` in championship.py. Keep in
# sync if the parallel agent's edits add new field reads.
SEASON_STATS_FIELDS: tuple[str, ...] = (
    "games_played",
    "total_points",
    "total_minutes",
    "total_fga",
    "total_fta",
    "total_assists",
)

ADVANCED_FIELDS: tuple[str, ...] = (
    "ts_pct",
    "usg_pct",
    "def_rating",
)

PLAY_TYPE_FIELDS: tuple[str, ...] = (
    "isolation_freq",
    "pnr_ball_handler_freq",
    "spot_up_freq",
)

CLUTCH_FIELDS: tuple[str, ...] = (
    "games_played",
    "pts",
    "fga",
    "fta",
    "net_rating",
)

COMPUTED_ADVANCED_FIELDS: tuple[str, ...] = (
    "obpm",
    "dbpm",
    "bpm",
)

# all-in-one fields the calculator reads via getattr()
ALL_IN_ONE_FIELDS: tuple[str, ...] = (
    "epm_offense",
    "rpm_offense",
    "lebron_offense",
    "darko_offense",
    "epm_defense",
    "rpm_defense",
    "lebron_defense",
    "darko_defense",
)


def _ns(fields: tuple[str, ...], values: dict[str, Any]) -> SimpleNamespace:
    """Build a SimpleNamespace where every required field exists (defaults to None)."""
    payload = {f: values.get(f) for f in fields}
    return SimpleNamespace(**payload)


def build_player_season_inputs(
    player_id: int | None,
    season: str,
    *,
    bbr_row: dict[str, Any] | None = None,
    teammate_bpm_lookup: dict[tuple[str, str], list[float]] | None = None,
    team: str | None = None,
) -> dict[str, Any]:
    """Assemble the kwargs dict for :class:`ChampionshipCalculator`.

    For modern seasons (2003+) we pull the box-score-adjacent inputs
    (``season_stats``, ``advanced``) from the NBA Stats API where possible,
    falling back to whatever Basketball Reference provided in ``bbr_row``.

    Play types are only available 2015+, clutch stats only 2018+, and the
    all-in-one impact aggregates only 2003+ (and not uniformly). Older
    seasons return ``None`` for those inputs so the calculator's fallbacks
    activate.

    Args:
        player_id:          NBA Stats PERSON_ID. May be ``None`` for older
                            seasons where we only know the BBR name.
        season:             Season string like ``"2015-16"``.
        bbr_row:            One row of the contender_controls parquet
                            (BPM, OBPM, DBPM, TS%, USG%, GP, MP). Optional.
        teammate_bpm_lookup: Map ``(season, team) -> [bpm of each rotation
                            teammate, target-player excluded, top-4 first]``.
                            Used to fill ``teammate_impact_scores``.
        team:               Team abbreviation; required to look up teammates.

    Returns:
        kwargs ready to splat into ``ChampionshipCalculator(**kwargs)``.
    """
    bbr = bbr_row or {}
    start_year = int(season.split("-")[0])

    # season_stats: derive totals from BBR (per-game BBR rows only give us
    # GP and MP directly; PTS/FGA/FTA/AST come from PerGame * GP if we
    # have them, else None and the calculator's safe_div / safe_float
    # defaults absorb the missing values).
    season_stats = _ns(
        SEASON_STATS_FIELDS,
        {
            "games_played": _safe_int(bbr.get("games")),
            "total_minutes": _safe_float(bbr.get("minutes")),
            "total_points": _safe_float(bbr.get("total_points")),
            "total_fga": _safe_float(bbr.get("total_fga")),
            "total_fta": _safe_float(bbr.get("total_fta")),
            "total_assists": _safe_float(bbr.get("total_assists")),
        },
    )

    advanced = _ns(
        ADVANCED_FIELDS,
        {
            "ts_pct": _safe_float(bbr.get("ts_pct")),
            "usg_pct": _safe_float(bbr.get("usg_pct")),
            "def_rating": _safe_float(bbr.get("def_rating")),
        },
    )

    computed_advanced = _ns(
        COMPUTED_ADVANCED_FIELDS,
        {
            "bpm": _safe_float(bbr.get("bpm")),
            "obpm": _safe_float(bbr.get("obpm")),
            "dbpm": _safe_float(bbr.get("dbpm")),
        },
    )

    # Pre-2015 seasons: no play-type tracking from NBA Stats.
    play_types = None
    # Pre-2018 seasons: no clutch endpoint coverage we can rely on.
    clutch_stats = None
    # Pre-2003 seasons: no aggregated all-in-one metrics. Even modern
    # seasons in our backtest are returned as None because pulling
    # historical EPM/LEBRON/DARKO is out of scope -- the calculator
    # falls back to OBPM/DBPM in that case.
    all_in_one = None

    on_off = None  # the calculator does not read on_off in the current code
    career_stats: list[Any] = []  # left empty -- experience pillar will use defaults

    teammate_impact_scores: list[float] = []
    if teammate_bpm_lookup is not None and team is not None:
        teammate_impact_scores = list(teammate_bpm_lookup.get((season, team), []))[:4]

    return {
        "season_stats": season_stats,
        "advanced": advanced,
        "play_types": play_types,
        "clutch_stats": clutch_stats,
        "on_off": on_off,
        "computed_advanced": computed_advanced,
        "all_in_one": all_in_one,
        "career_stats": career_stats,
        "portability_score": 50.0,
        "teammate_impact_scores": teammate_impact_scores,
        "_meta": {
            "season": season,
            "player_id": player_id,
            "start_year": start_year,
            "team": team,
        },
    }


def build_teammate_lookup(
    controls: list[dict[str, Any]] | pd.DataFrame,
) -> dict[tuple[str, str], list[float]]:
    """Group the controls dataset into ``(season, team) -> [BPM, ...]``.

    The returned lists are sorted descending so the calculator can take
    the top-N entries without resorting itself.

    Args:
        controls: Output of :func:`data_collection.fetch_contender_controls`,
            either as a list-of-dicts or a DataFrame.
    """
    if isinstance(controls, pd.DataFrame):
        records: list[dict[str, Any]] = controls.to_dict(orient="records")
    else:
        records = controls

    groups: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for r in records:
        team = r.get("team")
        bpm = r.get("bpm")
        if team is None or bpm is None:
            continue
        # BBR multi-team rows (TOT/2TM/3TM) are not real teammates -- skip.
        if str(team) in {"TOT", "2TM", "3TM"}:
            continue
        try:
            bpm_f = float(bpm)
        except (TypeError, ValueError):
            continue
        key = (str(r["season"]), str(team))
        groups.setdefault(key, []).append((str(r.get("player_name", "")), bpm_f))

    out: dict[tuple[str, str], list[float]] = {}
    for key, pairs in groups.items():
        pairs.sort(key=lambda p: -p[1])
        out[key] = [b for _, b in pairs]
    return out


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    return f


def _safe_int(v: Any) -> int | None:
    f = _safe_float(v)
    if f is None:
        return None
    return int(f)
