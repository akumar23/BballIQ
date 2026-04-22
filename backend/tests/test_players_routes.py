"""Route tests for the players endpoints.

Covers:
* ``/players/available`` legacy (bare-array) shape vs paginated envelope.
* ``/players/search`` ILIKE fallback path (SQLite in-memory has no pg_trgm).

Uses the shared in-memory SQLite engine + ``TestClient`` fixtures from
``conftest.py``. Seeding is done through a small ``_seed_players`` helper
that runs before the ``TestClient`` is created, matching the pattern
expected by the other route tests.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Player, PlayerCareerStats, SeasonStats


def _seed_players(session: Session) -> None:
    """Populate a small cast of players + career seasons + season stats."""
    players = [
        Player(
            id=1,
            nba_id=1001,
            name="LeBron James",
            position="F",
            team_abbreviation="LAL",
            active=True,
        ),
        Player(
            id=2,
            nba_id=1002,
            name="Stephen Curry",
            position="G",
            team_abbreviation="GSW",
            active=True,
        ),
        Player(
            id=3,
            nba_id=1003,
            name="Kevin Durant",
            position="F",
            team_abbreviation="PHX",
            active=True,
        ),
        Player(
            id=4,
            nba_id=1004,
            name="Retired Guy",
            position="G",
            team_abbreviation=None,
            active=False,
        ),
    ]
    session.add_all(players)
    session.flush()

    # SQLite's INTEGER PRIMARY KEY autoincrement doesn't cooperate with
    # BigInteger columns the same way Postgres does, so seed explicit ids.
    career_rows: list[PlayerCareerStats] = []
    next_id = 1
    for player in players:
        if not player.active:
            continue
        for season in ("2024-25", "2023-24"):
            career_rows.append(
                PlayerCareerStats(
                    id=next_id,
                    player_id=player.id,
                    season=season,
                    games_played=70,
                    team_abbreviation=player.team_abbreviation,
                )
            )
            next_id += 1
    session.add_all(career_rows)

    session.add_all(
        [
            SeasonStats(
                id=1,
                player_id=1,
                season="2024-25",
                games_played=70,
            ),
        ]
    )


def _client(
    seeded_session: Callable[..., Session],
    make_client: Callable[[], TestClient],
) -> TestClient:
    """Seed the shared DB engine and return a live TestClient."""
    session = seeded_session(_seed_players)
    session.close()
    return make_client()


class TestAvailablePlayersLegacy:
    """The bare-array response shape is preserved when no paging params are sent."""

    def test_returns_bare_array_without_params(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/available")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        # 3 active players * 2 seasons each
        assert len(body) == 6
        # Sorted by name ascending, then season descending
        names = [row["name"] for row in body]
        assert names == sorted(names)
        # Each entry carries a season string
        assert all("season" in row for row in body)

    def test_excludes_inactive_players(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/available")
        assert resp.status_code == 200
        names = {row["name"] for row in resp.json()}
        assert "Retired Guy" not in names


class TestAvailablePlayersPaginated:
    """Passing ``limit`` or ``offset`` opts into the envelope response."""

    def test_envelope_shape_when_limit_passed(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/available?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["limit"] == 2
        assert body["offset"] == 0
        assert body["total"] == 6
        assert len(body["items"]) == 2

    def test_envelope_shape_when_offset_passed(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/available?offset=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["offset"] == 2
        assert body["limit"] == 50  # default when only offset is passed
        assert body["total"] == 6
        assert len(body["items"]) == 4

    def test_offset_skips_correctly(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        full = client.get("/api/players/available").json()
        page_one = client.get("/api/players/available?limit=2&offset=0").json()
        page_two = client.get("/api/players/available?limit=2&offset=2").json()
        assert [i["id"] for i in page_one["items"]] == [r["id"] for r in full[:2]]
        assert [i["id"] for i in page_two["items"]] == [r["id"] for r in full[2:4]]

    def test_limit_validation(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        # limit=0 -> 422 (ge=1)
        assert client.get("/api/players/available?limit=0").status_code == 422
        # limit=501 -> 422 (le=500)
        assert client.get("/api/players/available?limit=501").status_code == 422
        # offset < 0 -> 422
        assert client.get("/api/players/available?offset=-1").status_code == 422


class TestPlayerSearch:
    """The search endpoint falls back to ILIKE when pg_trgm is unavailable."""

    def test_exact_substring_match(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/search?q=Curry")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Stephen Curry"
        # SQLite fallback path: similarity is always None
        assert body[0]["similarity"] is None

    def test_case_insensitive_match(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/search?q=lebron")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "LeBron James" in names

    def test_excludes_inactive(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/search?q=Retired")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_limit_param(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/search?q=e&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    def test_missing_q_is_422(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        assert client.get("/api/players/search").status_code == 422

    def test_empty_q_is_422(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        # min_length=1 rejects ""; trimming to "" after a non-empty q
        # (e.g. "   ") returns an empty list rather than 422.
        resp = client.get("/api/players/search?q=")
        assert resp.status_code == 422

    def test_whitespace_only_q_returns_empty(
        self,
        seeded_session: Callable[..., Session],
        make_client: Callable[[], TestClient],
    ) -> None:
        client = _client(seeded_session, make_client)
        resp = client.get("/api/players/search?q=%20%20%20")
        assert resp.status_code == 200
        assert resp.json() == []
