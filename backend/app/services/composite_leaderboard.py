"""Weighted z-score composite leaderboard.

Ranks players by a single composite score built from five stat categories.
Each category z-scores its constituent stats across the eligible player pool,
averages those z-scores, then multiplies by a category weight. Categories
(and weights) sum to 1.0.

Design notes:
    - Eligibility filter keeps scrub outliers out of the standardization pool;
      without it a 2-game rookie can distort means/stdevs.
    - Missing stats are treated as "not counted" for that player's category
      score rather than imputed to the mean, so a player missing half the
      stats in a category isn't silently given a typical score.
    - def_rating is inverted (negated) so lower = better aligns with the
      "higher z-score = better" convention.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Player, PlayerAdvancedStats, PlayerComputedAdvanced, SeasonStats

# Stat accessor signature: (season_stats, advanced, computed) -> float | None.
# Keeps the category config declarative and composable.
StatExtractor = callable  # type: ignore[assignment]


@dataclass(frozen=True)
class StatSpec:
    key: str
    extractor: StatExtractor
    # Set True for stats where lower is better (e.g. defensive rating). The
    # extractor's value is negated before z-scoring so the "higher z = better"
    # convention holds.
    lower_is_better: bool = False


@dataclass(frozen=True)
class CategorySpec:
    key: str
    weight: float
    stats: tuple[StatSpec, ...]


def _as_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _per_game(total, gp) -> float | None:
    if total is None or not gp:
        return None
    return float(total) / float(gp)


# Category definitions. Weights sum to 1.0.
CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec(
        key="scoring",
        weight=0.25,
        stats=(
            StatSpec("ppg", lambda s, a, c: _per_game(s.total_points, s.games_played)),
            StatSpec("ts_pct", lambda s, a, c: _as_float(a.ts_pct) if a else None),
            StatSpec("usg_pct", lambda s, a, c: _as_float(a.usg_pct) if a else None),
        ),
    ),
    CategorySpec(
        key="playmaking",
        weight=0.20,
        stats=(
            StatSpec("apg", lambda s, a, c: _per_game(s.total_assists, s.games_played)),
            StatSpec("ast_pct", lambda s, a, c: _as_float(a.ast_pct) if a else None),
            StatSpec("ast_to", lambda s, a, c: _as_float(a.ast_to) if a else None),
        ),
    ),
    CategorySpec(
        key="rebounding",
        weight=0.15,
        stats=(
            StatSpec("rpg", lambda s, a, c: _per_game(s.total_rebounds, s.games_played)),
            StatSpec("oreb_pct", lambda s, a, c: _as_float(a.oreb_pct) if a else None),
            StatSpec("dreb_pct", lambda s, a, c: _as_float(a.dreb_pct) if a else None),
        ),
    ),
    CategorySpec(
        key="defense",
        weight=0.20,
        stats=(
            StatSpec("spg", lambda s, a, c: _per_game(s.total_steals, s.games_played)),
            StatSpec("bpg", lambda s, a, c: _per_game(s.total_blocks, s.games_played)),
            StatSpec(
                "def_rating",
                lambda s, a, c: _as_float(a.def_rating) if a else None,
                lower_is_better=True,
            ),
        ),
    ),
    CategorySpec(
        key="impact",
        weight=0.20,
        stats=(
            StatSpec("bpm", lambda s, a, c: _as_float(c.bpm) if c else None),
            StatSpec("ws_per_48", lambda s, a, c: _as_float(c.ws_per_48) if c else None),
            StatSpec("net_rating", lambda s, a, c: _as_float(a.net_rating) if a else None),
        ),
    ),
)


@dataclass
class PlayerRow:
    player: Player
    season_stats: SeasonStats
    advanced: PlayerAdvancedStats | None
    computed: PlayerComputedAdvanced | None


@dataclass
class RankedPlayer:
    player: Player
    season_stats: SeasonStats
    composite_score: float
    rank: int
    category_scores: dict[str, float]


def _z_scores(values: Iterable[float]) -> dict[int, float]:
    """Compute z-scores keyed by the caller's index. Stdev of 0 → all zeros."""
    indexed = list(enumerate(values))
    if not indexed:
        return {}
    raw = [v for _, v in indexed]
    mean = statistics.fmean(raw)
    stdev = statistics.pstdev(raw) if len(raw) > 1 else 0.0
    if stdev == 0:
        return {i: 0.0 for i, _ in indexed}
    return {i: (v - mean) / stdev for i, v in indexed}


def _fetch_rows(db: Session, season: str, min_games: int, min_mpg: float) -> list[PlayerRow]:
    # One pass: season_stats with outer joins to advanced + computed so we
    # don't have to issue N+1 queries per player.
    query = (
        db.query(Player, SeasonStats, PlayerAdvancedStats, PlayerComputedAdvanced)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .outerjoin(
            PlayerAdvancedStats,
            (PlayerAdvancedStats.player_id == Player.id)
            & (PlayerAdvancedStats.season == season),
        )
        .outerjoin(
            PlayerComputedAdvanced,
            (PlayerComputedAdvanced.player_id == Player.id)
            & (PlayerComputedAdvanced.season == season),
        )
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.games_played >= min_games)
    )
    rows: list[PlayerRow] = []
    for player, season_stats, advanced, computed in query.all():
        gp = season_stats.games_played or 0
        mpg = float(season_stats.total_minutes) / gp if gp and season_stats.total_minutes else 0.0
        if mpg < min_mpg:
            continue
        rows.append(PlayerRow(player, season_stats, advanced, computed))
    return rows


def compute_composite_rankings(
    db: Session,
    season: str,
    limit: int = 50,
    min_games: int = 15,
    min_mpg: float = 15.0,
) -> list[RankedPlayer]:
    """Rank eligible players for ``season`` by weighted z-score composite.

    Args:
        db: Open SQLAlchemy session.
        season: Season in ``YYYY-YY`` form.
        limit: How many top players to return.
        min_games: Minimum games played to be eligible.
        min_mpg: Minimum minutes per game to be eligible.

    Returns:
        Top ``limit`` players ranked by composite_score descending. Each row
        also carries its per-category score for UI breakdowns.
    """
    rows = _fetch_rows(db, season, min_games, min_mpg)
    if not rows:
        return []

    # For each (category, stat): compute a z-score across every eligible
    # player that has that stat. Result indexed by (cat_key, stat_key, row_idx).
    stat_z: dict[tuple[str, str], dict[int, float]] = {}
    for cat in CATEGORIES:
        for spec in cat.stats:
            present_values: list[float] = []
            present_indices: list[int] = []
            for idx, row in enumerate(rows):
                raw = spec.extractor(row.season_stats, row.advanced, row.computed)
                if raw is None:
                    continue
                value = -float(raw) if spec.lower_is_better else float(raw)
                present_values.append(value)
                present_indices.append(idx)
            z_map = _z_scores(present_values)
            stat_z[(cat.key, spec.key)] = {
                present_indices[i]: z for i, z in z_map.items()
            }

    # Per-player: category score = mean of z-scores for the stats they have.
    # Missing entire category contributes 0 (no signal either way).
    ranked: list[RankedPlayer] = []
    for idx, row in enumerate(rows):
        category_scores: dict[str, float] = {}
        composite = 0.0
        for cat in CATEGORIES:
            per_stat_zs: list[float] = []
            for spec in cat.stats:
                z_map = stat_z[(cat.key, spec.key)]
                if idx in z_map:
                    per_stat_zs.append(z_map[idx])
            cat_score = statistics.fmean(per_stat_zs) if per_stat_zs else 0.0
            category_scores[cat.key] = cat_score
            composite += cat.weight * cat_score
        ranked.append(
            RankedPlayer(
                player=row.player,
                season_stats=row.season_stats,
                composite_score=composite,
                rank=0,  # assigned after sort
                category_scores=category_scores,
            )
        )

    ranked.sort(key=lambda r: r.composite_score, reverse=True)
    for i, r in enumerate(ranked[:limit], start=1):
        r.rank = i
    return ranked[:limit]
