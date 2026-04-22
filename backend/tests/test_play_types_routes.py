"""Route tests for :mod:`app.api.routes.play_types`.

Covers:

- ``GET /play-types/leaderboard`` for multiple play types + sort_by combos.
- ``GET /play-types/players/{player_id}`` success + 404.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.models import Player, SeasonPlayTypeStats

_CURRENT = get_current_season()


def _seed_play_type_rows(session: Session) -> None:
    """Seed three players with isolation + spot-up totals in the current season.

    The seeding is designed so ``isolation`` and ``spot_up`` orderings differ,
    which lets us assert that the play_type query param actually changes
    the leaderboard ordering.
    """
    session.add_all(
        [
            Player(id=1, nba_id=4001, name="Iso Ace", position="G",
                   team_abbreviation="IOS", active=True),
            Player(id=2, nba_id=4002, name="Spot Up King", position="F",
                   team_abbreviation="SUK", active=True),
            Player(id=3, nba_id=4003, name="Balanced Beast", position="F",
                   team_abbreviation="BAL", active=True),
        ]
    )
    session.flush()

    session.add_all(
        [
            SeasonPlayTypeStats(
                id=1, player_id=1, season=_CURRENT, total_poss=500,
                isolation_poss=300, isolation_pts=330,
                isolation_ppp=Decimal("1.100"),
                isolation_fg_pct=Decimal("0.480"),
                isolation_freq=Decimal("0.600"),
                spot_up_poss=100, spot_up_pts=90,
                spot_up_ppp=Decimal("0.900"),
                spot_up_fg_pct=Decimal("0.400"),
                spot_up_freq=Decimal("0.200"),
            ),
            SeasonPlayTypeStats(
                id=2, player_id=2, season=_CURRENT, total_poss=400,
                isolation_poss=60, isolation_pts=48,
                isolation_ppp=Decimal("0.800"),
                isolation_fg_pct=Decimal("0.380"),
                isolation_freq=Decimal("0.150"),
                spot_up_poss=300, spot_up_pts=360,
                spot_up_ppp=Decimal("1.200"),
                spot_up_fg_pct=Decimal("0.500"),
                spot_up_freq=Decimal("0.750"),
            ),
            SeasonPlayTypeStats(
                id=3, player_id=3, season=_CURRENT, total_poss=450,
                isolation_poss=150, isolation_pts=150,
                isolation_ppp=Decimal("1.000"),
                isolation_fg_pct=Decimal("0.450"),
                isolation_freq=Decimal("0.333"),
                spot_up_poss=150, spot_up_pts=150,
                spot_up_ppp=Decimal("1.000"),
                spot_up_fg_pct=Decimal("0.450"),
                spot_up_freq=Decimal("0.333"),
            ),
        ]
    )


class TestPlayTypeLeaderboard:
    def test_isolation_ordering_by_ppp(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get(
            "/api/play-types/leaderboard?play_type=isolation&sort_by=ppp"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["play_type"] == "Isolation"
        assert body["sort_by"] == "ppp"
        # Player 2 has iso_poss=60 < min_poss=50? No, 60 >= 50 so included.
        # Iso PPP: Iso Ace(1.10) > Balanced(1.00) > Spot Up King(0.80)
        ids = [entry["id"] for entry in body["entries"]]
        assert ids == [1, 3, 2]
        # Ranks are 1-indexed
        assert [entry["rank"] for entry in body["entries"]] == [1, 2, 3]

    def test_spot_up_ordering_by_ppp(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get(
            "/api/play-types/leaderboard?play_type=spot_up&sort_by=ppp"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["play_type"] == "Spot-Up"
        # Spot-up PPP: SUK(1.20) > Balanced(1.00) > Iso Ace(0.90)
        assert [entry["id"] for entry in body["entries"]] == [2, 3, 1]

    def test_min_poss_filter_excludes_low_volume_players(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get(
            "/api/play-types/leaderboard?play_type=isolation&min_poss=200"
        )
        assert resp.status_code == 200
        # Only Iso Ace has isolation_poss >= 200 (300)
        assert [entry["id"] for entry in resp.json()["entries"]] == [1]

    def test_invalid_play_type_returns_422(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get("/api/play-types/leaderboard?play_type=bogus")
        assert resp.status_code == 422


class TestPlayerPlayTypes:
    def test_returns_player_payload(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get("/api/play-types/players/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 1
        assert body["season"] == _CURRENT
        assert body["total_poss"] == 500
        assert body["isolation"]["possessions"] == 300
        assert body["isolation"]["ppp"] == "1.100"
        # Spot-up carries the extra fg3 fields (schema = SpotUpMetrics)
        assert "fg3m" in body["spot_up"]

    def test_unknown_player_id_is_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        seeded_session(_seed_play_type_rows).close()
        client = make_client()
        resp = client.get("/api/play-types/players/99999")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Player not found"

    def test_player_exists_but_no_stats_is_404(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        def _seed_player_only(session: Session) -> None:
            session.add(
                Player(
                    id=10, nba_id=4999, name="No Stats", position="G",
                    team_abbreviation="NOP", active=True,
                )
            )

        seeded_session(_seed_player_only).close()
        client = make_client()
        resp = client.get("/api/play-types/players/10")
        assert resp.status_code == 404
        assert "Play type stats not found" in resp.json()["detail"]
