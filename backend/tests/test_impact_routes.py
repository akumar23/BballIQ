"""Route tests for :mod:`app.api.routes.impact`.

Covers:

- ``GET /impact/leaderboard`` — success path, ``sort_by`` switching,
  season override, empty-result season.
- ``GET /impact/players/{player_id}`` — success path, 404 on unknown player.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.models import ContextualizedImpact, Player, PlayerOnOffStats

_CURRENT = get_current_season()
_PRIOR = "2022-23"


def _seed_impact_rows(session: Session) -> None:
    """Seed three players with impact + on/off rows in the current season."""
    session.add_all(
        [
            Player(id=1, nba_id=3001, name="Alpha", position="G",
                   team_abbreviation="ATL", active=True),
            Player(id=2, nba_id=3002, name="Bravo", position="F",
                   team_abbreviation="BOS", active=True),
            Player(id=3, nba_id=3003, name="Charlie", position="C",
                   team_abbreviation="CHI", active=True),
        ]
    )
    session.flush()

    # On/off rows — required for the ``/impact/players`` endpoint's filter
    # on ``on_court_minutes.isnot(None)``.
    session.add_all(
        [
            PlayerOnOffStats(
                id=1, player_id=1, season=_CURRENT,
                on_court_minutes=Decimal("1200.00"),
                on_court_net_rating=Decimal("8.50"),
                net_rating_diff=Decimal("5.00"),
            ),
            PlayerOnOffStats(
                id=2, player_id=2, season=_CURRENT,
                on_court_minutes=Decimal("1100.00"),
                on_court_net_rating=Decimal("6.00"),
                net_rating_diff=Decimal("3.00"),
            ),
            PlayerOnOffStats(
                id=3, player_id=3, season=_CURRENT,
                on_court_minutes=Decimal("900.00"),
                on_court_net_rating=Decimal("-1.50"),
                net_rating_diff=Decimal("-2.00"),
            ),
        ]
    )

    session.add_all(
        [
            ContextualizedImpact(
                id=1, player_id=1, season=_CURRENT,
                raw_net_rating_diff=Decimal("5.00"),
                raw_off_rating_diff=Decimal("4.00"),
                raw_def_rating_diff=Decimal("-1.00"),
                contextualized_net_impact=Decimal("7.50"),
                contextualized_off_impact=Decimal("6.00"),
                contextualized_def_impact=Decimal("-1.50"),
                teammate_adjustment=Decimal("-0.50"),
                reliability_factor=Decimal("0.90"),
                impact_percentile=95,
            ),
            ContextualizedImpact(
                id=2, player_id=2, season=_CURRENT,
                raw_net_rating_diff=Decimal("3.00"),
                raw_off_rating_diff=Decimal("2.00"),
                raw_def_rating_diff=Decimal("-1.00"),
                contextualized_net_impact=Decimal("4.00"),
                contextualized_off_impact=Decimal("8.00"),
                contextualized_def_impact=Decimal("-4.00"),
                reliability_factor=Decimal("0.80"),
                impact_percentile=75,
            ),
            ContextualizedImpact(
                id=3, player_id=3, season=_CURRENT,
                raw_net_rating_diff=Decimal("-2.00"),
                contextualized_net_impact=Decimal("-1.00"),
                contextualized_off_impact=Decimal("-2.00"),
                contextualized_def_impact=Decimal("-6.00"),
                reliability_factor=Decimal("0.70"),
                impact_percentile=50,
            ),
            # Prior-season row for player 1 to exercise ``season=`` override.
            ContextualizedImpact(
                id=4, player_id=1, season=_PRIOR,
                raw_net_rating_diff=Decimal("1.00"),
                contextualized_net_impact=Decimal("2.00"),
                impact_percentile=60,
            ),
        ]
    )


class TestImpactLeaderboard:
    def test_orders_by_net_impact_desc_by_default(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get("/api/impact/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        # contextualized_net_impact: 7.5 > 4 > -1 → players 1, 2, 3
        assert [row["id"] for row in body] == [1, 2, 3]

    def test_sort_by_offense(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get("/api/impact/leaderboard?sort_by=offense")
        assert resp.status_code == 200
        # off_impact: 8 > 6 > -2 → ids 2, 1, 3
        assert [row["id"] for row in resp.json()] == [2, 1, 3]

    def test_season_override(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get(f"/api/impact/leaderboard?season={_PRIOR}")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == 1

    def test_empty_season_returns_empty_list(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get("/api/impact/leaderboard?season=1900-01")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_invalid_sort_by_is_422(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        assert (
            client.get("/api/impact/leaderboard?sort_by=bogus").status_code == 422
        )


class TestPlayerImpact:
    def test_returns_player_payload(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get("/api/impact/players/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["name"] == "Alpha"
        assert body["season"] == _CURRENT
        assert body["impact"]["contextualized_net_impact"] == "7.50"
        assert body["on_off_stats"]["on_court_minutes"] == "1200.00"

    def test_unknown_player_id_is_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_impact_rows).close()
        client = make_client()
        resp = client.get("/api/impact/players/9999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Player not found"
