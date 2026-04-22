"""Route tests for :mod:`app.api.routes.advanced_stats`.

Covers:

- ``GET /stats/advanced`` — paginated list keyed off ``net_rating``.
- ``GET /stats/advanced/{player_id}`` — success + 404.
- ``GET /stats/shot-zones/{player_id}`` — success + 404 for both
  player-not-found and no-zone-data cases.
- ``GET /stats/defense/leaderboard`` — sorts by ``pct_plusminus`` ASC,
  with ``sort_by`` switching between rim / overall / three_point.
- ``GET /stats/defense/{player_id}`` — success + 404.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.models import Player
from app.models.advanced_stats import PlayerAdvancedStats
from app.models.clutch_stats import PlayerClutchStats
from app.models.defensive_matchups import PlayerDefensiveStats
from app.models.shot_zones import PlayerShotZones

_CURRENT = get_current_season()


def _seed_advanced_rows(session: Session) -> None:
    session.add_all(
        [
            Player(id=1, nba_id=5001, name="Alpha", position="G",
                   team_abbreviation="ATL", active=True),
            Player(id=2, nba_id=5002, name="Bravo", position="F",
                   team_abbreviation="BOS", active=True),
            Player(id=3, nba_id=5003, name="Charlie", position="C",
                   team_abbreviation="CHI", active=True),
        ]
    )
    session.flush()

    session.add_all(
        [
            PlayerAdvancedStats(
                id=1, player_id=1, season=_CURRENT,
                ts_pct=Decimal("0.620"), efg_pct=Decimal("0.580"),
                usg_pct=Decimal("0.280"),
                off_rating=Decimal("118.5"), def_rating=Decimal("108.0"),
                net_rating=Decimal("10.5"),
            ),
            PlayerAdvancedStats(
                id=2, player_id=2, season=_CURRENT,
                ts_pct=Decimal("0.590"), efg_pct=Decimal("0.540"),
                usg_pct=Decimal("0.240"),
                off_rating=Decimal("115.0"), def_rating=Decimal("110.0"),
                net_rating=Decimal("5.0"),
            ),
            PlayerAdvancedStats(
                id=3, player_id=3, season=_CURRENT,
                ts_pct=Decimal("0.550"), efg_pct=Decimal("0.510"),
                usg_pct=Decimal("0.200"),
                off_rating=Decimal("110.0"), def_rating=Decimal("112.5"),
                net_rating=Decimal("-2.5"),
            ),
        ]
    )

    session.add_all(
        [
            PlayerClutchStats(
                id=1, player_id=1, season=_CURRENT,
                games_played=30, pts=Decimal("4.10"),
                fgm=Decimal("1.40"), fga=Decimal("3.10"),
                fg_pct=Decimal("0.450"),
            ),
        ]
    )

    session.add_all(
        [
            PlayerShotZones(
                id=1, player_id=1, season=_CURRENT, zone="Restricted Area",
                fgm=Decimal("5.50"), fga=Decimal("8.00"),
                fg_pct=Decimal("0.688"), freq=Decimal("0.420"),
                league_avg=Decimal("0.650"),
            ),
            PlayerShotZones(
                id=2, player_id=1, season=_CURRENT, zone="Above the Break 3",
                fgm=Decimal("2.20"), fga=Decimal("6.00"),
                fg_pct=Decimal("0.367"), freq=Decimal("0.310"),
                league_avg=Decimal("0.360"),
            ),
        ]
    )

    # Defensive rows — values chosen so that ``pct_plusminus`` is negative
    # (good defender) in descending-strength order.
    session.add_all(
        [
            PlayerDefensiveStats(
                id=1, player_id=1, season=_CURRENT,
                overall_pct_plusminus=Decimal("-0.040"),
                rim_pct_plusminus=Decimal("-0.070"),
                three_pt_pct_plusminus=Decimal("-0.020"),
                overall_d_fgm=Decimal("5.00"),
                overall_d_fga=Decimal("12.00"),
                overall_d_fg_pct=Decimal("0.416"),
            ),
            PlayerDefensiveStats(
                id=2, player_id=2, season=_CURRENT,
                overall_pct_plusminus=Decimal("-0.010"),
                rim_pct_plusminus=Decimal("-0.030"),
                three_pt_pct_plusminus=Decimal("-0.015"),
                overall_d_fgm=Decimal("4.00"),
                overall_d_fga=Decimal("10.00"),
                overall_d_fg_pct=Decimal("0.400"),
            ),
            PlayerDefensiveStats(
                id=3, player_id=3, season=_CURRENT,
                overall_pct_plusminus=Decimal("0.030"),
                rim_pct_plusminus=Decimal("0.010"),
                three_pt_pct_plusminus=Decimal("0.005"),
                overall_d_fgm=Decimal("6.00"),
                overall_d_fga=Decimal("11.50"),
                overall_d_fg_pct=Decimal("0.522"),
            ),
        ]
    )


class TestAdvancedStatsList:
    def test_returns_players_ordered_by_net_rating_desc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/advanced")
        assert resp.status_code == 200
        body = resp.json()
        assert [row["id"] for row in body] == [1, 2, 3]
        assert body[0]["advanced"]["net_rating"] == "10.5"

    def test_limit_and_offset(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/advanced?limit=1&offset=1")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == 2


class TestPlayerAdvancedStats:
    def test_success(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/advanced/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["advanced"]["ts_pct"] == "0.620"
        # Player 1 has a clutch row; non-null nested payload.
        assert body["clutch"] is not None
        assert body["clutch"]["games_played"] == 30

    def test_404_for_unknown_player(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/advanced/9999")
        assert resp.status_code == 404


class TestPlayerShotZones:
    def test_success(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/shot-zones/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        zone_names = {z["zone"] for z in body["zones"]}
        assert zone_names == {"Restricted Area", "Above the Break 3"}

    def test_unknown_player_is_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/shot-zones/9999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Player not found"

    def test_player_without_zones_is_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        # Player 2 exists but has no shot_zones rows.
        resp = client.get("/api/stats/shot-zones/2")
        assert resp.status_code == 404
        assert "Shot zone data not found" in resp.json()["detail"]


class TestDefensiveLeaderboard:
    def test_sorts_by_overall_pct_plusminus_asc(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/defense/leaderboard")
        assert resp.status_code == 200
        body = resp.json()
        # overall pct_plusminus: -0.04 (best) < -0.01 < 0.03 → ids 1, 2, 3
        assert [row["id"] for row in body] == [1, 2, 3]

    def test_sort_by_rim(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/defense/leaderboard?sort_by=rim")
        assert resp.status_code == 200
        body = resp.json()
        # rim pct_plusminus: -0.07 < -0.03 < 0.01 → ids 1, 2, 3
        assert [row["id"] for row in body] == [1, 2, 3]

    def test_invalid_sort_by_422(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/defense/leaderboard?sort_by=neck")
        assert resp.status_code == 422


class TestPlayerDefensiveProfile:
    def test_success(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/defense/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["overall"]["pct_plusminus"] == "-0.040"

    def test_unknown_player_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_advanced_rows).close()
        client = make_client()
        resp = client.get("/api/stats/defense/9999")
        assert resp.status_code == 404
