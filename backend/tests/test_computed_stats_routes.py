"""Route tests for :mod:`app.api.routes.computed_stats`.

Covers:

- ``GET /stats/computed`` — paginated list sorted by PER.
- ``GET /stats/computed/{player_id}`` — success + 404.
- ``GET /stats/career/{player_id}`` — success (all seasons asc) + 404.
- ``GET /stats/shooting`` — paginated list sorted by catch_shoot_pts.
- ``GET /stats/shooting/{player_id}`` — success + 404.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.models import Player
from app.models.career_stats import PlayerCareerStats
from app.models.computed_advanced import PlayerComputedAdvanced
from app.models.shooting_tracking import PlayerShootingTracking

_CURRENT = get_current_season()


def _seed_computed_rows(session: Session) -> None:
    session.add_all(
        [
            Player(id=1, nba_id=6001, name="Alpha", position="G",
                   team_abbreviation="ATL", active=True),
            Player(id=2, nba_id=6002, name="Bravo", position="F",
                   team_abbreviation="BOS", active=True),
            Player(id=3, nba_id=6003, name="Charlie", position="C",
                   team_abbreviation="CHI", active=True),
        ]
    )
    session.flush()

    session.add_all(
        [
            PlayerComputedAdvanced(
                id=1, player_id=1, season=_CURRENT,
                per=Decimal("28.50"), bpm=Decimal("8.00"),
                vorp=Decimal("5.00"), ws=Decimal("10.50"),
                radar_scoring=92,
            ),
            PlayerComputedAdvanced(
                id=2, player_id=2, season=_CURRENT,
                per=Decimal("22.00"), bpm=Decimal("4.00"),
                vorp=Decimal("3.10"), ws=Decimal("7.00"),
                radar_scoring=78,
            ),
            PlayerComputedAdvanced(
                id=3, player_id=3, season=_CURRENT,
                per=Decimal("17.50"), bpm=Decimal("1.50"),
                vorp=Decimal("1.20"), ws=Decimal("4.00"),
                radar_scoring=60,
            ),
        ]
    )

    session.add_all(
        [
            PlayerCareerStats(
                id=1, player_id=1, season="2021-22",
                games_played=70, minutes=Decimal("30.5"),
                ppg=Decimal("20.1"), rpg=Decimal("5.0"), apg=Decimal("6.0"),
                team_abbreviation="ATL",
            ),
            PlayerCareerStats(
                id=2, player_id=1, season="2022-23",
                games_played=72, minutes=Decimal("32.0"),
                ppg=Decimal("22.4"), rpg=Decimal("5.5"), apg=Decimal("6.3"),
                team_abbreviation="ATL",
            ),
            PlayerCareerStats(
                id=3, player_id=1, season=_CURRENT,
                games_played=65, minutes=Decimal("33.0"),
                ppg=Decimal("25.8"), rpg=Decimal("6.0"), apg=Decimal("6.8"),
                team_abbreviation="ATL",
            ),
        ]
    )

    session.add_all(
        [
            PlayerShootingTracking(
                id=1, player_id=1, season=_CURRENT,
                catch_shoot_fga=Decimal("4.50"),
                catch_shoot_pts=Decimal("5.50"),
                pullup_fga=Decimal("8.00"),
                drives=Decimal("15.50"),
            ),
            PlayerShootingTracking(
                id=2, player_id=2, season=_CURRENT,
                catch_shoot_fga=Decimal("5.20"),
                catch_shoot_pts=Decimal("7.20"),
                pullup_fga=Decimal("4.50"),
                drives=Decimal("10.00"),
            ),
        ]
    )


class TestComputedStatsList:
    def test_sorted_by_per_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/computed")
        assert resp.status_code == 200
        body = resp.json()
        assert [row["id"] for row in body] == [1, 2, 3]
        assert body[0]["computed"]["per"] == "28.50"
        assert body[0]["radar"]["scoring"] == 92

    def test_limit_offset(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/computed?limit=1&offset=2")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == 3


class TestPlayerComputedStats:
    def test_success(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/computed/2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 2
        assert body["computed"]["per"] == "22.00"

    def test_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        assert client.get("/api/stats/computed/99").status_code == 404


class TestPlayerCareer:
    def test_returns_seasons_in_ascending_order(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/career/1")
        assert resp.status_code == 200
        body = resp.json()
        seasons = [row["season"] for row in body["seasons"]]
        assert seasons == sorted(seasons), "career seasons are sorted ascending"
        assert len(seasons) == 3

    def test_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        assert client.get("/api/stats/career/99").status_code == 404


class TestShootingTracking:
    def test_ordered_by_catch_shoot_pts_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/shooting")
        assert resp.status_code == 200
        body = resp.json()
        # catch_shoot_pts: Bravo 7.2 > Alpha 5.5
        assert [row["id"] for row in body] == [2, 1]

    def test_per_player_success(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        resp = client.get("/api/stats/shooting/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["shooting"]["drives"] == "15.50"

    def test_per_player_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_computed_rows).close()
        client = make_client()
        assert client.get("/api/stats/shooting/99").status_code == 404
