"""Route tests for :mod:`app.api.routes.leaderboards`.

Covers the offensive / defensive / overall / per-game / seasons endpoints.

Every endpoint is ``@cache``-decorated (60s TTL) via ``fastapi-cache2``. The
shared ``make_client`` fixture installs an in-process ``InMemoryBackend``
so we can exercise the cache path deterministically — a second request
should hit the cache even after the seeded rows are deleted in between.

All endpoints default-fall-back to ``get_current_season()`` when the
``season`` query param is omitted; the fixture seeds rows into the
season returned by ``get_current_season()`` so the fallback path is
exercised without freezing the clock.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.models import Player, SeasonStats

_CURRENT = get_current_season()
_PRIOR = "2022-23"


def _make_player(pid: int, name: str, team: str, nba_id: int) -> Player:
    return Player(
        id=pid,
        nba_id=nba_id,
        name=name,
        position="F",
        team_abbreviation=team,
        active=True,
    )


def _make_season_stats(
    stat_id: int,
    player_id: int,
    season: str,
    *,
    off: Decimal | None = None,
    def_: Decimal | None = None,
    overall: Decimal | None = None,
    games_played: int = 70,
    total_points: int | None = None,
    total_rebounds: int | None = None,
    total_assists: int | None = None,
    total_minutes: Decimal | None = None,
) -> SeasonStats:
    return SeasonStats(
        id=stat_id,
        player_id=player_id,
        season=season,
        games_played=games_played,
        offensive_metric=off,
        defensive_metric=def_,
        overall_metric=overall,
        total_points=total_points,
        total_rebounds=total_rebounds,
        total_assists=total_assists,
        total_minutes=total_minutes,
    )


def _seed_leaderboard_rows(session: Session) -> None:
    """Seed three players with season stats across two seasons.

    The current-season rows are arranged so offensive / defensive / overall
    have distinct orderings, making it easy to assert the ``order_by`` contract.
    """
    session.add_all(
        [
            _make_player(1, "Alpha Alpha", "ATL", 2001),
            _make_player(2, "Bravo Bravo", "BOS", 2002),
            _make_player(3, "Charlie Charlie", "CHI", 2003),
        ]
    )
    session.flush()

    session.add_all(
        [
            # Current season
            _make_season_stats(
                1, 1, _CURRENT,
                off=Decimal("95.00"), def_=Decimal("60.00"), overall=Decimal("81.00"),
                total_points=1800, total_rebounds=400, total_assists=500,
                total_minutes=Decimal("2400.00"),
            ),
            _make_season_stats(
                2, 2, _CURRENT,
                off=Decimal("85.00"), def_=Decimal("80.00"), overall=Decimal("83.00"),
                total_points=1500, total_rebounds=700, total_assists=200,
                total_minutes=Decimal("2100.00"),
            ),
            _make_season_stats(
                3, 3, _CURRENT,
                off=Decimal("70.00"), def_=Decimal("90.00"), overall=Decimal("78.00"),
                total_points=1200, total_rebounds=600, total_assists=300,
                total_minutes=Decimal("2000.00"),
            ),
            # Prior season — just enough to exercise the season override path.
            _make_season_stats(
                4, 1, _PRIOR,
                off=Decimal("10.00"), def_=Decimal("10.00"), overall=Decimal("10.00"),
                total_points=500, total_rebounds=200, total_assists=150,
                total_minutes=Decimal("1500.00"),
            ),
        ]
    )


class TestOffensiveLeaderboard:
    def test_orders_by_offensive_metric_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/offensive")
        assert resp.status_code == 200
        body = resp.json()
        assert [row["id"] for row in body] == [1, 2, 3]
        assert body[0]["metrics"]["offensive_metric"] == "95.00"

    def test_limit_query_param(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/offensive?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_limit_validation_rejects_over_100(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        assert client.get("/api/leaderboards/offensive?limit=101").status_code == 422


class TestDefensiveLeaderboard:
    def test_orders_by_defensive_metric_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/defensive")
        assert resp.status_code == 200
        body = resp.json()
        # Defensive ordering is: Charlie(90) > Bravo(80) > Alpha(60)
        assert [row["id"] for row in body] == [3, 2, 1]


class TestOverallLeaderboard:
    def test_orders_by_overall_metric_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/overall")
        assert resp.status_code == 200
        # Overall: Bravo(83) > Alpha(81) > Charlie(78)
        assert [row["id"] for row in resp.json()] == [2, 1, 3]


class TestSeasonOverride:
    def test_season_query_param_returns_prior_season_rows(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get(f"/api/leaderboards/offensive?season={_PRIOR}")
        assert resp.status_code == 200
        body = resp.json()
        # Only player 1 has a prior-season row
        assert len(body) == 1
        assert body[0]["id"] == 1

    def test_empty_season_returns_empty_list(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/offensive?season=1900-01")
        assert resp.status_code == 200
        assert resp.json() == []


class TestPerGameLeaderboard:
    def test_sorts_by_ppg_by_default(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/per-game")
        assert resp.status_code == 200
        body = resp.json()
        # PPG: 1800/70 > 1500/70 > 1200/70 → ids 1, 2, 3
        assert [row["id"] for row in body] == [1, 2, 3]
        assert pytest.approx(float(body[0]["ppg"])) == 25.7

    def test_sorts_by_rpg_when_sort_by_rpg(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/per-game?sort_by=rpg")
        body = resp.json()
        # RPG: 700/70 > 600/70 > 400/70 → ids 2, 3, 1
        assert [row["id"] for row in body] == [2, 3, 1]


class TestSeasonsList:
    def test_returns_distinct_seasons_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_leaderboard_rows).close()
        client = make_client()
        resp = client.get("/api/leaderboards/seasons")
        assert resp.status_code == 200
        seasons = [row["season"] for row in resp.json()]
        # _CURRENT is always lexicographically >= _PRIOR (YYYY-YY is sortable)
        assert seasons == sorted(seasons, reverse=True)
        assert _CURRENT in seasons
        assert _PRIOR in seasons


class TestLeaderboardCaching:
    """The endpoint is ``@cache(expire=60)`` — a repeat request hits the cache."""

    def test_second_request_served_from_cache_after_rows_deleted(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        session = seeded_session(_seed_leaderboard_rows)
        try:
            client = make_client()
            first = client.get("/api/leaderboards/offensive").json()
            assert len(first) == 3

            # Wipe the rows out from under the cache; the cached response
            # should still be returned verbatim.
            session.query(SeasonStats).delete()
            session.commit()

            second = client.get("/api/leaderboards/offensive").json()
            assert second == first, "InMemoryBackend should serve the cached body"
        finally:
            session.close()
