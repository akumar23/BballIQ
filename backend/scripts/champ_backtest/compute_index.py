"""Score historical rows using the production ``ChampionshipCalculator``.

Two functions:

* :func:`compute_for_row` -- run the calculator on a single
  ``contender_controls`` row, returning ``ChampionshipResult | None``.
* :func:`score_dataset`   -- vectorised wrapper that returns a tidy
  DataFrame (one row per player-season, columns = pillar scores +
  composite index + win prob + label).

We deliberately call the *current* production calculator rather than
re-implementing pillar logic. That way improvements to it (e.g. the
parallel agent's Bayesian-shrinkage clutch fix) flow into the harness
automatically.

Because the calculator's :class:`ChampionshipResult` may grow new
fields (the spec mentions ``path_viability``), :func:`_result_to_dict`
introspects the dataclass at runtime instead of hardcoding field names.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.championship import ChampionshipCalculator, ChampionshipResult

from scripts.champ_backtest.feature_extraction import (
    build_player_season_inputs,
    build_teammate_lookup,
)

logger = logging.getLogger(__name__)

SCORED_PATH = Path(__file__).resolve().parent / "cache" / "scored.parquet"


def compute_for_row(
    row: dict[str, Any],
    teammate_lookup: dict[tuple[str, str], list[float]] | None = None,
) -> ChampionshipResult | None:
    """Score a single contender_controls row.

    Args:
        row: One record from the controls dataset (must contain ``season``
            and ``player_name``; other fields fill what they can).
        teammate_lookup: Output of :func:`feature_extraction.build_teammate_lookup`.

    Returns:
        :class:`ChampionshipResult` on success, or ``None`` if the row
        lacks enough data (e.g. all numeric fields missing) for the
        calculator to produce a non-trivial result.
    """
    try:
        # Drop the target player's own BPM out of their teammate list before
        # passing it through. The lookup is keyed by (season, team) and the
        # lists are sorted by BPM desc; we filter by removing the highest
        # BPM that matches the row's own BPM (best effort).
        kwargs = build_player_season_inputs(
            player_id=row.get("player_id"),
            season=str(row["season"]),
            bbr_row=row,
            teammate_bpm_lookup=teammate_lookup,
            team=row.get("team"),
        )
        kwargs.pop("_meta", None)

        own_bpm = row.get("bpm")
        if own_bpm is not None and kwargs["teammate_impact_scores"]:
            try:
                own_bpm_f = float(own_bpm)
            except (TypeError, ValueError):
                own_bpm_f = None
            if own_bpm_f is not None:
                # Remove first occurrence of own BPM (within float tolerance).
                tolerance = 1e-6
                trimmed = []
                removed = False
                for b in kwargs["teammate_impact_scores"]:
                    if not removed and abs(b - own_bpm_f) < tolerance:
                        removed = True
                        continue
                    trimmed.append(b)
                kwargs["teammate_impact_scores"] = trimmed[:4]

        calc = ChampionshipCalculator(**kwargs)
        return calc.calculate()
    except Exception as exc:
        logger.warning(
            "scoring failed for %s / %s: %s",
            row.get("season"),
            row.get("player_name"),
            exc,
        )
        return None


def score_dataset(
    rows: list[dict[str, Any]] | pd.DataFrame,
    *,
    persist: bool = True,
) -> pd.DataFrame:
    """Apply :func:`compute_for_row` to every row, returning a tidy DataFrame.

    Args:
        rows:    The contender_controls dataset (list-of-dicts or DataFrame).
        persist: If True, write the resulting DataFrame to
            ``cache/scored.parquet`` (idempotent caching for resumability).

    Returns:
        DataFrame with one row per scored player-season. Columns:
        ``season``, ``player_name``, ``team``, ``won_title``,
        every pillar field on :class:`ChampionshipResult`,
        plus ``championship_index``, ``win_probability``, ``multiplier_vs_base``,
        ``tier``.
    """
    if isinstance(rows, pd.DataFrame):
        records = rows.to_dict(orient="records")
    else:
        records = list(rows)

    teammate_lookup = build_teammate_lookup(records)

    out_rows: list[dict[str, Any]] = []
    skipped = 0
    for r in records:
        result = compute_for_row(r, teammate_lookup)
        if result is None:
            skipped += 1
            continue
        out_rows.append(
            {
                "season": r.get("season"),
                "player_name": r.get("player_name"),
                "team": r.get("team"),
                "won_title": bool(r.get("won_title", False)),
                **_result_to_dict(result),
            }
        )

    df = pd.DataFrame(out_rows)
    logger.info("scored %d rows (%d skipped)", len(df), skipped)

    if persist and not df.empty:
        SCORED_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(SCORED_PATH, index=False)
        logger.info("wrote scored DataFrame to %s", SCORED_PATH)
    return df


def _result_to_dict(result: ChampionshipResult) -> dict[str, Any]:
    """Convert a :class:`ChampionshipResult` to a flat dict.

    Done dynamically via :func:`dataclasses.fields` so the harness keeps
    working when the parallel agent adds new fields like ``path_viability``.
    """
    out: dict[str, Any] = {}
    for f in dataclasses.fields(result):
        out[f.name] = getattr(result, f.name)
    return out


def pillar_field_names(result: ChampionshipResult | None = None) -> list[str]:
    """Return the dataclass field names that look like pillar scores.

    A pillar is any float field that is not the composite index, win
    probability, multiplier, or tier label. Auto-detected so we transparently
    handle the ``supporting_cast`` removal in the parallel branch.
    """
    if result is None:
        # Default-construct a dummy result so we can introspect the fields
        # without needing input data.
        result = ChampionshipResult()
    excluded = {
        "championship_index",
        "tier",
        "win_probability",
        "multiplier_vs_base",
        "path_viability",
    }
    pillars: list[str] = []
    for f in dataclasses.fields(result):
        if f.name in excluded:
            continue
        if f.type in (float, "float"):
            pillars.append(f.name)
        else:
            # Fallback: include any non-string runtime value
            val = getattr(result, f.name, None)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                pillars.append(f.name)
    return pillars
