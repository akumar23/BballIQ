"""Happy-path + retry-narrowing tests for the remaining celery refresh tasks.

``tests/test_data_refresh.py`` already covers:

- ``daily_data_refresh`` chord orchestration (happy + failure),
- ``_after_group_phase`` roll-up,
- ``refresh_impact_data`` savepoint + threshold loop,
- ``_finalize_task_status`` helper.

This module fills in the gaps for the other four sibling tasks plus
``recalculate_metrics``. For each task:

- A happy-path test stubs the NBA client + the SQLAlchemy ``Session`` via
  :class:`_FakeSession`, runs the task synchronously (``task_always_eager``),
  and asserts that the expected number of upserts landed on the session.
- A retry-narrowing assertion verifies that ``ValueError`` is **not** in
  ``_RETRY_EXCEPTIONS`` while ``requests.RequestException`` **is**.

We don't spin up a real DB — the tests rely on the same ``_FakeSession``
shape as ``test_data_refresh.py`` so refresh logic that only cares about
savepoints + execute calls can be exercised without Postgres.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest
import requests
import sqlalchemy.exc

from app.core.celery_app import celery_app
from app.services.rate_limiter import CircuitBreakerError, RateLimitError
from app.tasks import data_refresh, metrics

# ---------------------------------------------------------------------------
# Shared fake session + query plumbing (kept small and task-agnostic)
# ---------------------------------------------------------------------------


class _FakeSavepoint:
    """Context manager mirroring ``Session.begin_nested()`` semantics."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> _FakeSavepoint:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False


class _FakeQuery:
    """Query double: ``first()`` yields a player-like mock, ``all()`` is empty."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def filter(self, *_a: Any, **_kw: Any) -> _FakeQuery:
        return self

    def first(self) -> Any:
        player = MagicMock()
        player.id = self._session.current_player_id or 1
        return player

    def all(self) -> list[Any]:
        return []


class _FakeSession:
    """Session double sufficient for refresh tasks that only call:

    - ``begin_nested()``
    - ``commit()`` / ``rollback()`` / ``close()``
    - ``query(Player).filter(...).first()``
    - ``execute(stmt)`` (captured for assertions)
    """

    def __init__(self) -> None:
        self.savepoints: list[_FakeSavepoint] = []
        self.commits = 0
        self.rollbacks = 0
        self.executes: list[Any] = []
        self.closed = False
        self.current_player_id: int | None = None

    def begin_nested(self) -> _FakeSavepoint:
        sp = _FakeSavepoint()
        self.savepoints.append(sp)
        return sp

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True

    def query(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return _FakeQuery(self)

    def execute(self, stmt: Any) -> Any:
        self.executes.append(stmt)
        result = MagicMock()
        result.scalar_one.return_value = 1
        return result


@pytest.fixture(autouse=True)
def _celery_eager() -> Iterator[None]:
    """Run Celery tasks synchronously so ``.apply()`` returns a real result."""
    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_prop


# ---------------------------------------------------------------------------
# Retry-set assertion shared across all tasks in this module.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryNarrowing:
    """Every refresh task shares the module-level ``_RETRY_EXCEPTIONS`` tuple."""

    def test_programming_errors_not_retried(self) -> None:
        """ValueError / TypeError / KeyError must not be in the retry set."""
        retry = data_refresh._RETRY_EXCEPTIONS
        for exc in (ValueError, TypeError, KeyError, AttributeError):
            assert not issubclass(exc, retry), (
                f"{exc.__name__} should fail fast, not retry"
            )

    def test_transient_network_and_db_errors_retried(self) -> None:
        retry = data_refresh._RETRY_EXCEPTIONS
        assert CircuitBreakerError in retry
        assert RateLimitError in retry
        assert requests.RequestException in retry
        assert sqlalchemy.exc.OperationalError in retry
        assert sqlalchemy.exc.InterfaceError in retry


# ---------------------------------------------------------------------------
# refresh_impact_data happy-path (savepoint/loop is already tested in
# test_data_refresh.py; here we just assert the non-error return payload).
# ---------------------------------------------------------------------------


def _make_on_off_dict(ids: list[int]) -> dict[int, Any]:
    from app.services.nba_data import PlayerOnOffData

    zero = Decimal("0")
    return {
        pid: PlayerOnOffData(
            player_id=pid, player_name=f"P{pid}", team_id=1,
            team_abbreviation="TST",
            on_court_min=Decimal("500"), on_court_plus_minus=zero,
            on_court_off_rating=zero, on_court_def_rating=zero,
            on_court_net_rating=zero,
            off_court_min=Decimal("500"), off_court_plus_minus=zero,
            off_court_off_rating=zero, off_court_def_rating=zero,
            off_court_net_rating=zero,
            plus_minus_diff=zero, off_rating_diff=zero,
            def_rating_diff=zero, net_rating_diff=zero,
        )
        for pid in ids
    }


@pytest.mark.unit
class TestRefreshImpactDataHappyPath:
    def test_all_rows_succeed_returns_success_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        on_off = _make_on_off_dict([1, 2, 3])
        fake_service = MagicMock()
        fake_service.fetch_lineup_data.return_value = {}
        fake_service.get_all_on_off_stats.return_value = on_off

        fake_calc = MagicMock()
        fake_calc.calculate_all_impacts.return_value = {}

        monkeypatch.setattr(
            "app.services.nba_data.NBADataService",
            MagicMock(return_value=fake_service),
        )
        monkeypatch.setattr(
            "app.services.impact_calculator.ImpactCalculator",
            MagicMock(return_value=fake_calc),
        )

        fake_db = _FakeSession()
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=fake_db)
        )

        payload = data_refresh.refresh_impact_data.apply(args=[None]).get()

        assert payload["status"] == "success"
        assert payload["processed"] == 3
        assert payload["errors"] == 0
        # Each of 3 players triggers one on-off execute (no impact_data, so
        # only one insert per player).
        assert len(fake_db.executes) == 3
        # All savepoints committed.
        assert all(sp.committed for sp in fake_db.savepoints)
        assert fake_db.closed is True


# ---------------------------------------------------------------------------
# refresh_play_type_data
# ---------------------------------------------------------------------------


def _make_play_type_data(ids: list[int]) -> dict[int, Any]:
    """Build a dict of ``PlayerPlayTypeData`` with a single spot-up metric set."""
    from app.services.nba_data import PlayerPlayTypeData, PlayTypeMetrics

    return {
        pid: PlayerPlayTypeData(
            player_id=pid,
            player_name=f"P{pid}",
            team_abbreviation="TST",
            spot_up=PlayTypeMetrics(
                possessions=120, points=144, fgm=50, fga=100,
                fg3m=30, fg3a=75,
            ),
            total_poss=400,
        )
        for pid in ids
    }


@pytest.mark.unit
class TestRefreshPlayTypeData:
    def test_happy_path_upserts_one_row_per_player(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_service = MagicMock()
        fake_service.fetch_all_play_type_data.return_value = _make_play_type_data(
            [1, 2]
        )

        monkeypatch.setattr(
            "app.services.nba_data.NBADataService",
            MagicMock(return_value=fake_service),
        )

        fake_db = _FakeSession()
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=fake_db)
        )

        payload = data_refresh.refresh_play_type_data.apply(args=[None]).get()

        assert payload["status"] == "success"
        assert payload["processed"] == 2
        assert payload["errors"] == 0
        # 1 upsert per player.
        assert len(fake_db.executes) == 2
        assert all(sp.committed for sp in fake_db.savepoints)
        assert fake_db.closed is True

    def test_fetch_raising_non_retryable_error_does_not_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ValueError is NOT in ``_RETRY_EXCEPTIONS`` → task fails fast."""
        fake_service = MagicMock()
        fake_service.fetch_all_play_type_data.side_effect = ValueError("bad data")

        monkeypatch.setattr(
            "app.services.nba_data.NBADataService",
            MagicMock(return_value=fake_service),
        )
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=_FakeSession())
        )

        # ``ValueError`` is not in ``autoretry_for`` → eager propagation raises.
        with pytest.raises(ValueError, match="bad data"):
            data_refresh.refresh_play_type_data.apply(args=[None]).get()

    def test_request_exception_is_in_retry_set(self) -> None:
        """Sanity guard: transient network errors are retried."""
        assert requests.RequestException in data_refresh._RETRY_EXCEPTIONS


# ---------------------------------------------------------------------------
# refresh_advanced_data — broad surface; we stub each fetch method and
# assert that the ``all_player_ids`` union drives the expected upsert count.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRefreshAdvancedData:
    @staticmethod
    def _patch_service(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        fake_service = MagicMock()
        fake_service.get_advanced_stats.return_value = [
            {"PLAYER_ID": 1, "TS_PCT": "0.61"},
            {"PLAYER_ID": 2, "TS_PCT": "0.55"},
        ]
        fake_service.get_clutch_stats.return_value = [
            {"PLAYER_ID": 1, "GP": 10, "PTS": "3.1"},
        ]
        fake_service.get_defensive_stats.return_value = [
            {"CLOSE_DEF_PERSON_ID": 1, "D_FGM": "5"},
        ]
        fake_service.get_rim_protection_stats.return_value = [
            {"CLOSE_DEF_PERSON_ID": 1, "D_FGM": "2"},
        ]
        fake_service.get_three_point_defense_stats.return_value = []
        fake_service.get_defensive_play_type_stats.return_value = []
        fake_service.get_shot_location_stats.return_value = []
        fake_service.get_league_shot_averages.return_value = {}

        monkeypatch.setattr(
            "app.services.nba_data.NBADataService",
            MagicMock(return_value=fake_service),
        )
        return fake_service

    def test_happy_path_processes_union_of_player_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_service(monkeypatch)

        fake_db = _FakeSession()
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=fake_db)
        )

        # Also stub scripts.shared since the task imports from it.
        monkeypatch.setattr(
            "scripts.shared.safe_decimal",
            lambda v: Decimal(str(v)) if v is not None else None,
        )
        monkeypatch.setattr(
            "scripts.shared.safe_int", lambda v: int(v) if v is not None else None
        )

        payload = data_refresh.refresh_advanced_data.apply(args=[None]).get()

        # Union of player ids: {1, 2} from advanced + clutch/defense on 1.
        assert payload["status"] == "success"
        assert payload["processed"] == 2
        assert payload["errors"] == 0
        assert payload["shot_zones_total"] == 0
        # Player 1 has advanced + clutch + defensive (3 upserts);
        # player 2 has only advanced (1 upsert).
        assert len(fake_db.executes) == 4
        assert fake_db.closed is True

    def test_advanced_fetch_value_error_fails_fast(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_service = MagicMock()
        fake_service.get_advanced_stats.side_effect = ValueError("boom")
        monkeypatch.setattr(
            "app.services.nba_data.NBADataService",
            MagicMock(return_value=fake_service),
        )
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=_FakeSession())
        )

        with pytest.raises(ValueError, match="boom"):
            data_refresh.refresh_advanced_data.apply(args=[None]).get()


# ---------------------------------------------------------------------------
# refresh_phase2_data — delegates to ``scripts.fetch_phase2_data`` helpers.
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRefreshPhase2Data:
    def test_happy_path_aggregates_subphase_results(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.nba_data.NBADataService", MagicMock()
        )
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=_FakeSession())
        )
        monkeypatch.setattr(
            "scripts.fetch_phase2_data.fetch_and_store_shooting_tracking",
            lambda season, db, svc: {"processed": 10, "errors": 0},
        )
        monkeypatch.setattr(
            "scripts.fetch_phase2_data.compute_and_store_metrics",
            lambda season, db, svc: {"stored": 20, "errors": 0},
        )
        monkeypatch.setattr(
            "scripts.fetch_phase2_data.fetch_and_store_career_stats",
            lambda db, svc, career_limit=50: {"processed": 5, "errors": 0},
        )

        payload = data_refresh.refresh_phase2_data.apply(args=[None]).get()

        assert payload["status"] == "success"
        # 10 + 20 + 5 = 35
        assert payload["processed"] == 35
        assert payload["errors"] == 0
        assert payload["part_a"] == {"processed": 10, "errors": 0}

    def test_value_error_fails_fast(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.nba_data.NBADataService", MagicMock()
        )
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=_FakeSession())
        )

        def _boom(*_a: Any, **_kw: Any) -> dict[str, object]:
            raise ValueError("phase2 bad")

        monkeypatch.setattr(
            "scripts.fetch_phase2_data.fetch_and_store_shooting_tracking", _boom
        )
        monkeypatch.setattr(
            "scripts.fetch_phase2_data.compute_and_store_metrics",
            lambda season, db, svc: {"stored": 0, "errors": 0},
        )
        monkeypatch.setattr(
            "scripts.fetch_phase2_data.fetch_and_store_career_stats",
            lambda db, svc, career_limit=50: {"processed": 0, "errors": 0},
        )

        with pytest.raises(ValueError, match="phase2 bad"):
            data_refresh.refresh_phase2_data.apply(args=[None]).get()


# ---------------------------------------------------------------------------
# recalculate_metrics — lives in ``app.tasks.metrics`` but conceptually part
# of the refresh pipeline.
# ---------------------------------------------------------------------------


class _FakeSeasonStats:
    """Minimal attribute bag with all the fields ``recalculate_metrics`` reads."""

    def __init__(self, player_id: int) -> None:
        self.player_id = player_id
        self.total_touches = 100
        self.total_assists = 10
        self.total_turnovers = 5
        self.total_fta = 8
        self.avg_points_per_touch = Decimal("0.5")
        self.estimated_possessions = 200
        self.total_deflections = 4
        self.total_contested_shots = 20
        self.total_charges_drawn = 2
        self.total_loose_balls_recovered = 6
        self.total_steals = 15
        self.offensive_metric: Decimal | None = None
        self.defensive_metric: Decimal | None = None
        self.overall_metric: Decimal | None = None
        self.offensive_percentile: int | None = None
        self.defensive_percentile: int | None = None


class _FakeMetricsQuery:
    """Query stub that returns the pre-seeded list on ``.all()``."""

    def __init__(self, rows: list[_FakeSeasonStats]) -> None:
        self._rows = rows

    def filter(self, *_a: Any, **_kw: Any) -> _FakeMetricsQuery:
        return self

    def all(self) -> list[_FakeSeasonStats]:
        return list(self._rows)


class _FakeMetricsSession:
    def __init__(self, rows: list[_FakeSeasonStats]) -> None:
        self._rows = rows
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        # Successive ``query(...).filter(...).all()`` calls: first for
        # ``recalculate_metrics``, second+ for ``_recalculate_percentiles``.
        self._call_count = 0

    def query(self, *_a: Any, **_kw: Any) -> _FakeMetricsQuery:
        self._call_count += 1
        return _FakeMetricsQuery(self._rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


@pytest.mark.unit
class TestRecalculateMetrics:
    def test_happy_path_updates_each_row(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [_FakeSeasonStats(pid) for pid in range(1, 4)]
        fake_db = _FakeMetricsSession(rows)
        monkeypatch.setattr(
            metrics, "SessionLocal", MagicMock(return_value=fake_db)
        )

        result = metrics.recalculate_metrics.apply(args=["2024-25"]).get()

        assert result["status"] == "success"
        assert result["players_updated"] == 3
        assert result["errors"] == 0
        # Every row got its derived metrics populated.
        assert all(row.offensive_metric is not None for row in rows)
        assert all(row.defensive_metric is not None for row in rows)
        assert fake_db.closed is True

    def test_warning_when_no_rows_for_season(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_db = _FakeMetricsSession(rows=[])
        monkeypatch.setattr(
            metrics, "SessionLocal", MagicMock(return_value=fake_db)
        )

        result = metrics.recalculate_metrics.apply(args=["1999-00"]).get()
        assert result["status"] == "warning"
        assert "No stats found" in result["message"]
