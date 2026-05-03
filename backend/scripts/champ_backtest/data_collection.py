"""Historical data collection for the Championship Index backtest.

This module pulls two datasets from network sources (NBA Stats API and
Basketball Reference) and persists them as parquet files under
``cache/`` so subsequent runs can resume without hitting the network.

Outputs (cache files):
    title_winners.parquet   -- one row per championship: season, team,
                               champion_player_name, champion_player_id.
    contender_controls.parquet -- top-N players by regular-season BPM
                                  for every season in [start_year, end_year],
                                  tagged with ``won_title`` boolean.

Usage:
    >>> from scripts.champ_backtest import data_collection
    >>> winners = data_collection.fetch_title_winners()
    >>> controls = data_collection.fetch_contender_controls(top_n_per_year=15)

DO NOT actually run end-to-end during ad-hoc development -- the BBR scrape
politely sleeps 3-5 seconds per request and the full 1985-2025 sweep takes
a couple of hours.
"""

from __future__ import annotations

import logging
import random
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent / "cache"
TITLE_WINNERS_PATH = CACHE_DIR / "title_winners.parquet"
CONTROLS_PATH = CACHE_DIR / "contender_controls.parquet"

BBR_BASE = "https://www.basketball-reference.com"
BBR_SLEEP_SECONDS = 3.5  # be polite -- BBR rate-limits at ~20 req/min

# ---------------------------------------------------------------------------
# Hardcoded fallback for pre-1996 champions.
#
# NBA Stats API coverage of playoff PlayerGameLogs is patchy before 1996-97;
# rather than guess at the #1 option from incomplete logs, we hardcode the
# era's well-known finals MVPs / leading playoff scorers. Player IDs are the
# canonical NBA Stats IDs (PERSON_ID from the players index).
# ---------------------------------------------------------------------------
PRE_1996_CHAMPIONS: list[dict[str, Any]] = [
    # season, team, champion_player_name, champion_player_id
    {"season": "1984-85", "team": "LAL", "champion_player_name": "Magic Johnson", "champion_player_id": 77142},
    {"season": "1985-86", "team": "BOS", "champion_player_name": "Larry Bird", "champion_player_id": 1449},
    {"season": "1986-87", "team": "LAL", "champion_player_name": "Magic Johnson", "champion_player_id": 77142},
    {"season": "1987-88", "team": "LAL", "champion_player_name": "Magic Johnson", "champion_player_id": 77142},
    {"season": "1988-89", "team": "DET", "champion_player_name": "Isiah Thomas", "champion_player_id": 78318},
    {"season": "1989-90", "team": "DET", "champion_player_name": "Isiah Thomas", "champion_player_id": 78318},
    {"season": "1990-91", "team": "CHI", "champion_player_name": "Michael Jordan", "champion_player_id": 893},
    {"season": "1991-92", "team": "CHI", "champion_player_name": "Michael Jordan", "champion_player_id": 893},
    {"season": "1992-93", "team": "CHI", "champion_player_name": "Michael Jordan", "champion_player_id": 893},
    {"season": "1993-94", "team": "HOU", "champion_player_name": "Hakeem Olajuwon", "champion_player_id": 165},
    {"season": "1994-95", "team": "HOU", "champion_player_name": "Hakeem Olajuwon", "champion_player_id": 165},
    {"season": "1995-96", "team": "CHI", "champion_player_name": "Michael Jordan", "champion_player_id": 893},
]


def _ensure_cache_dir() -> None:
    """Create the cache dir if it does not yet exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _season_str(start_year: int) -> str:
    """Convert a starting calendar year (e.g. 2015) to ``"2015-16"``."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _start_year_from_season(season: str) -> int:
    """Inverse of :func:`_season_str`: ``"2015-16"`` -> ``2015``."""
    return int(season.split("-")[0])


def _polite_sleep(base: float = BBR_SLEEP_SECONDS) -> None:
    """Sleep with a tiny jitter so we do not hammer BBR in a tight loop."""
    time.sleep(base + random.uniform(0, 0.5))


# ---------------------------------------------------------------------------
# Title winners
# ---------------------------------------------------------------------------


def fetch_title_winners(
    start_year: int = 1985,
    end_year: int = 2025,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return one record per championship in ``[start_year, end_year]``.

    Each record has the schema::

        {
            "season":               "2015-16",
            "team":                 "CLE",
            "champion_player_name": "LeBron James",
            "champion_player_id":   2544,
        }

    Pre-1996 entries come from :data:`PRE_1996_CHAMPIONS` (NBA Stats API
    coverage is unreliable in that era). For 1996-97 onward we identify the
    champion team via :class:`nba_api.stats.endpoints.LeagueStandings` and
    pick the rotation player with the highest playoff PPG x GP product
    using :class:`nba_api.stats.endpoints.PlayerGameLogs`.

    Args:
        start_year: First season's starting year (inclusive). 1985 = 1984-85.
        end_year:   Last season's starting year (inclusive). 2025 = 2024-25.
        refresh:    If ``False`` and the parquet cache exists, load it instead
                    of hitting the network.

    Returns:
        A list of dicts (also persisted to ``cache/title_winners.parquet``).
    """
    _ensure_cache_dir()
    if not refresh and TITLE_WINNERS_PATH.exists():
        logger.info("loading cached title winners from %s", TITLE_WINNERS_PATH)
        df = pd.read_parquet(TITLE_WINNERS_PATH)
        return list(df.to_dict(orient="records"))

    rows: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        season = _season_str(year)
        if year < 1996:
            match = next((r for r in PRE_1996_CHAMPIONS if r["season"] == season), None)
            if match:
                rows.append(match)
            continue

        try:
            row = _fetch_title_winner_modern(season)
        except Exception as exc:  # pragma: no cover - depends on live API
            logger.warning("failed to fetch %s champion: %s", season, exc)
            continue
        if row:
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_parquet(TITLE_WINNERS_PATH, index=False)
    logger.info("wrote %d title-winner rows to %s", len(rows), TITLE_WINNERS_PATH)
    return rows


def _fetch_title_winner_modern(season: str) -> dict[str, Any] | None:
    """Identify the champion team and #1 option via the NBA Stats API.

    The "champion team" is whichever roster the Finals MVP played for.
    Rather than parsing the Finals series, we leverage the fact that
    :class:`PlayerGameLogs` with ``season_type_nullable="Playoffs"`` only
    returns games up through the Finals -- so the team that played the
    most playoff games in ``season`` is the champion. This breaks for the
    bubble year (2019-20 had a unique format) but the heuristic still
    selects the right team because the Lakers played 21 playoff games.

    The #1 option is the rotation player (>= 8 playoff GP) on the
    champion team with the highest ``PTS * GP`` product. This is more
    robust than usage rate, which is not reported in PlayerGameLogs.

    Args:
        season: Season string in ``"YYYY-YY"`` format (e.g. ``"2015-16"``).

    Returns:
        Same schema as :func:`fetch_title_winners`, or ``None`` on failure.
    """
    # Imported lazily so that `import data_collection` works in environments
    # without nba_api installed (e.g. the synthetic-test path).
    from nba_api.stats.endpoints import PlayerGameLogs

    logs_df = PlayerGameLogs(
        season_nullable=season,
        season_type_nullable="Playoffs",
    ).get_data_frames()[0]
    if logs_df.empty:
        logger.warning("empty playoff logs for %s", season)
        return None

    # Champion team = team that played the most playoff games this season.
    team_counts = logs_df.groupby("TEAM_ABBREVIATION")["GAME_ID"].nunique()
    champion_team = str(team_counts.idxmax())
    team_logs = logs_df[logs_df["TEAM_ABBREVIATION"] == champion_team]

    # Per-player playoff totals. PTS column in PlayerGameLogs is per-game
    # (it represents that game's stat line). Sum across games to get totals.
    per_player = team_logs.groupby(["PLAYER_ID", "PLAYER_NAME"]).agg(
        gp=("GAME_ID", "nunique"),
        total_pts=("PTS", "sum"),
    ).reset_index()
    per_player = per_player[per_player["gp"] >= 8]
    if per_player.empty:
        logger.warning("no rotation player found for %s on %s", season, champion_team)
        return None

    leader = per_player.sort_values("total_pts", ascending=False).iloc[0]
    return {
        "season": season,
        "team": champion_team,
        "champion_player_name": str(leader["PLAYER_NAME"]),
        "champion_player_id": int(leader["PLAYER_ID"]),
    }


# ---------------------------------------------------------------------------
# Contender controls (top-N by regular-season BPM)
# ---------------------------------------------------------------------------


def fetch_contender_controls(
    start_year: int = 1985,
    end_year: int = 2025,
    top_n_per_year: int = 15,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return the top-N players by regular-season BPM for each season.

    Schema::

        {
            "season":      "2015-16",
            "player_name": "Stephen Curry",
            "player_id":   201939,        # may be missing for pre-2000s rows
            "team":        "GSW",
            "bpm":         11.9,
            "obpm":        7.9,
            "dbpm":        4.0,
            "vorp":        9.8,
            "ts_pct":      0.669,
            "usg_pct":     0.323,
            "games":       79,
            "minutes":     2700,
            "won_title":   True,            # filled in via merge with winners
        }

    Pulled from Basketball Reference's per-season "Advanced" table.
    Polite 3-5s sleeps between season requests; cached as parquet.

    Args:
        start_year:     First season's starting year (inclusive).
        end_year:       Last season's starting year (inclusive).
        top_n_per_year: How many top-BPM players to retain per season.
        refresh:        If ``False`` and cache exists, load it instead.
    """
    _ensure_cache_dir()
    if not refresh and CONTROLS_PATH.exists():
        logger.info("loading cached contender controls from %s", CONTROLS_PATH)
        df = pd.read_parquet(CONTROLS_PATH)
        return list(df.to_dict(orient="records"))

    rows: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        season = _season_str(year)
        try:
            season_rows = _fetch_bbr_advanced_for_season(year, top_n_per_year)
        except Exception as exc:  # pragma: no cover - network-dependent
            logger.warning("failed to scrape BBR for %s: %s", season, exc)
            _polite_sleep()
            continue
        for r in season_rows:
            r["season"] = season
            r["won_title"] = False  # filled in below
        rows.extend(season_rows)
        _polite_sleep()

    # Tag winners.
    winners = fetch_title_winners(start_year, end_year, refresh=False)
    winner_keys = {(w["season"], w["champion_player_name"]) for w in winners}
    for r in rows:
        if (r["season"], r["player_name"]) in winner_keys:
            r["won_title"] = True

    # If a champion did not show up in the BBR top-N (rare -- a champion is
    # almost always a top-15 BPM player, but it can happen for older eras
    # or injury-shortened seasons), splice them in so the dataset has full
    # title coverage. We won't have BBR rows for them so we leave bpm = NaN
    # and the feature_extraction stage will pull what it can.
    seen = {(r["season"], r["player_name"]) for r in rows}
    for w in winners:
        key = (w["season"], w["champion_player_name"])
        if key not in seen:
            rows.append(
                {
                    "season": w["season"],
                    "player_name": w["champion_player_name"],
                    "player_id": w.get("champion_player_id"),
                    "team": w.get("team"),
                    "bpm": None,
                    "obpm": None,
                    "dbpm": None,
                    "vorp": None,
                    "ts_pct": None,
                    "usg_pct": None,
                    "games": None,
                    "minutes": None,
                    "won_title": True,
                }
            )

    df = pd.DataFrame(rows)
    df.to_parquet(CONTROLS_PATH, index=False)
    logger.info("wrote %d contender-control rows to %s", len(rows), CONTROLS_PATH)
    return rows


def _fetch_bbr_advanced_for_season(start_year: int, top_n: int) -> list[dict[str, Any]]:
    """Scrape the BBR "leagues/NBA_<year>_advanced.html" page.

    Args:
        start_year: Starting calendar year (e.g. 2016 for 2015-16).
            BBR URLs use the *ending* year, so we hit ``NBA_<start_year+1>_advanced.html``.
        top_n:      Number of top-BPM players to keep.

    Returns:
        List of dicts (without ``season`` or ``won_title`` -- the caller fills those in).
    """
    import requests
    from bs4 import BeautifulSoup

    end_year = start_year + 1
    url = f"{BBR_BASE}/leagues/NBA_{end_year}_advanced.html"
    headers = {"User-Agent": "champ-backtest-research/0.1 (kumar.aryan@gmail.com)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="advanced") or soup.find("table", id="advanced_stats")
    if table is None:
        raise RuntimeError(f"no advanced table at {url}")

    tbody = table.find("tbody") if hasattr(table, "find") else None
    if tbody is None:
        raise RuntimeError(f"advanced table at {url} has no <tbody>")

    rows: list[dict[str, Any]] = []
    for tr in tbody.find_all("tr"):
        if "thead" in (tr.get("class") or []):
            continue  # repeated header row
        name_cell = tr.find("td", {"data-stat": "player"}) or tr.find("td", {"data-stat": "name_display"})
        if name_cell is None:
            continue
        name = name_cell.get_text(strip=True)
        if not name:
            continue
        rows.append(
            {
                "player_name": name,
                "player_id": None,  # BBR has its own slug; left for feature_extraction
                "team": _td_text(tr, "team_id"),
                "bpm": _td_float(tr, "bpm"),
                "obpm": _td_float(tr, "obpm"),
                "dbpm": _td_float(tr, "dbpm"),
                "vorp": _td_float(tr, "vorp"),
                "ts_pct": _td_float(tr, "ts_pct"),
                "usg_pct": _td_float(tr, "usg_pct"),
                "games": _td_int(tr, "g"),
                "minutes": _td_int(tr, "mp"),
            }
        )

    # Players who were traded mid-season have multiple rows ("TOT" + each team);
    # keep only the TOT row for top-N selection.
    by_player: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r["player_name"]
        if key not in by_player or r["team"] in {"TOT", "2TM", "3TM"}:
            by_player[key] = r
    deduped = list(by_player.values())

    deduped.sort(key=lambda r: (r["bpm"] is None, -(r["bpm"] or -999)))
    return deduped[:top_n]


def _td_text(tr: Any, stat: str) -> str | None:
    cell = tr.find("td", {"data-stat": stat})
    if cell is None:
        return None
    val = cell.get_text(strip=True)
    return val or None


def _td_float(tr: Any, stat: str) -> float | None:
    val = _td_text(tr, stat)
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _td_int(tr: Any, stat: str) -> int | None:
    val = _td_text(tr, stat)
    if val is None:
        return None
    try:
        return int(val)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# CLI smoke-test entrypoint
# ---------------------------------------------------------------------------


def _main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Smoke entry point: ``python -m scripts.champ_backtest.data_collection``."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    winners = fetch_title_winners()
    controls = fetch_contender_controls()
    print(f"title winners: {len(winners)}", file=sys.stderr)
    print(f"control rows:  {len(controls)}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
