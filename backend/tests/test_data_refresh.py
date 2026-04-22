"""Tests for Celery refresh tasks in :mod:`app.tasks.data_refresh`.

These tests focus on the hardened control-flow introduced in Fix 3:

- per-player savepoints via ``db.begin_nested()`` isolate row-level failures,
- successful rows are committed in batches (batch size == ``BATCH_COMMIT_SIZE``),
- the task raises ``RuntimeError`` when the error-rate exceeds
  ``ERROR_THRESHOLD_RATIO`` so Celery marks the task failed instead of
  silently returning ``{"status": "success"}``.

The tests mock the NBA client and the SQLAlchemy ``Session`` — no Postgres
required — because existing test infra does not spin up a DB.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest

from app.core.celery_app import celery_app
from app.services.nba_data import PlayerOnOffData
from app.tasks import data_refresh
from app.tasks.data_refresh import refresh_impact_data


def _make_on_off(pid: int) -> PlayerOnOffData:
    """Build a minimal ``PlayerOnOffData`` instance for a test player."""
    zero = Decimal("0")
    return PlayerOnOffData(
        player_id=pid,
        player_name=f"Player {pid}",
        team_id=1,
        team_abbreviation="TST",
        on_court_min=Decimal("500"),
        on_court_plus_minus=zero,
        on_court_off_rating=zero,
        on_court_def_rating=zero,
        on_court_net_rating=zero,
        off_court_min=Decimal("500"),
        off_court_plus_minus=zero,
        off_court_off_rating=zero,
        off_court_def_rating=zero,
        off_court_net_rating=zero,
        plus_minus_diff=zero,
        off_rating_diff=zero,
        def_rating_diff=zero,
        net_rating_diff=zero,
    )


class _FakeSavepoint:
    """Minimal context manager that records whether the savepoint committed.

    SQLAlchemy's ``begin_nested()`` returns a context manager that rolls
    back on exception. We just need to mirror that so per-player failures
    don't abort the whole task under test.
    """

    def __init__(self, session: _FakeSession) -> None:
        self._session = session
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> _FakeSavepoint:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Literal[False]:
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        # Propagate exceptions like the real context manager does.
        return False


class _FakeSession:
    """Session double that captures control-flow interactions.

    Attributes:
        savepoints: Ordered list of savepoint context managers created via
            ``begin_nested()``. Each item carries ``committed``/``rolled_back``
            flags set by ``__exit__`` so the test can assert isolation.
        commits: Number of top-level ``commit()`` calls.
        rollbacks: Number of top-level ``rollback()`` calls.
        executes: Every SQL statement passed to ``execute()``.
        closed: True after the outer ``finally`` block calls ``close()``.
    """

    def __init__(self, raise_on_player_ids: set[int] | None = None) -> None:
        self.savepoints: list[_FakeSavepoint] = []
        self.commits = 0
        self.rollbacks = 0
        self.executes: list[Any] = []
        self.closed = False
        self._raise_on = raise_on_player_ids or set()
        self._current_player: int | None = None

    # --- SQLAlchemy-shaped helpers -----------------------------------

    def begin_nested(self) -> _FakeSavepoint:
        sp = _FakeSavepoint(self)
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
        # Return an object whose ``scalar_one`` returns a fake id — only used
        # by ``refresh_tracking_data``; harmless for other tasks.
        result = MagicMock()
        result.scalar_one.return_value = 1
        return result

    # Helpers for the fake query + ValueError injection. ``refresh_impact_data``
    # calls ``db.query(Player).filter(Player.nba_id == player_id).first()`` —
    # the fake ``_FakeQuery`` feeds it a player-like object and, when the
    # current player is in ``_raise_on``, injects a ValueError so the test
    # exercises the error-accounting branch.
    def set_current_player(self, pid: int) -> None:
        self._current_player = pid

    def maybe_raise(self) -> None:
        if self._current_player in self._raise_on:
            raise ValueError(f"synthetic failure for {self._current_player}")


class _FakeQuery:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def filter(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def first(self) -> Any:
        # Trigger the injected exception *before* returning a player so the
        # per-player block is still inside the savepoint when it raises.
        self._session.maybe_raise()
        player = MagicMock()
        player.id = self._session._current_player
        return player

    def all(self) -> list[Any]:
        return []


@pytest.fixture(autouse=True)
def _celery_eager() -> Iterator[None]:
    """Run Celery tasks synchronously so ``.apply()`` returns the real result."""
    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_prop


def _patch_impact_service(
    monkeypatch: pytest.MonkeyPatch,
    on_off_data: dict[int, PlayerOnOffData],
) -> None:
    """Mock NBADataService + ImpactCalculator used inside ``refresh_impact_data``."""
    fake_service = MagicMock()
    fake_service.fetch_lineup_data.return_value = {}
    fake_service.get_all_on_off_stats.return_value = on_off_data

    fake_calculator = MagicMock()
    fake_calculator.calculate_all_impacts.return_value = {}

    # Patch at the import paths used inside the task body.
    monkeypatch.setattr(
        "app.services.nba_data.NBADataService",
        MagicMock(return_value=fake_service),
    )
    monkeypatch.setattr(
        "app.services.impact_calculator.ImpactCalculator",
        MagicMock(return_value=fake_calculator),
    )


@pytest.mark.unit
class TestRefreshImpactDataHardening:
    """Verify Fix 3: savepoints, batched commits, error-threshold enforcement."""

    def test_raises_runtime_error_when_error_rate_exceeds_threshold(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """2/5 player rows fail → 40% > 10% threshold → RuntimeError."""
        on_off_data = {pid: _make_on_off(pid) for pid in range(1, 6)}
        raise_ids = {2, 4}

        fake_db = _FakeSession(raise_on_player_ids=raise_ids)

        # The task iterates ``on_off_data.items()`` in insertion order; the
        # wrapping dict stashes the active player id on the fake session so
        # the synthetic ValueError fires on the right rows.
        class _TrackingDict(dict[int, PlayerOnOffData]):
            def items(self) -> Any:
                for pid, on_off in super().items():
                    fake_db.set_current_player(pid)
                    yield pid, on_off

        tracking_dict = _TrackingDict(on_off_data)

        _patch_impact_service(monkeypatch, tracking_dict)
        monkeypatch.setattr(
            data_refresh, "SessionLocal", MagicMock(return_value=fake_db)
        )

        # Run the task synchronously; task_eager_propagates=True re-raises.
        with pytest.raises(RuntimeError, match=r"2/5 players failed"):
            refresh_impact_data.apply(args=[None]).get()

        # --- Savepoint isolation: one per player, 3 committed, 2 rolled back
        assert len(fake_db.savepoints) == 5
        committed = [sp for sp in fake_db.savepoints if sp.committed]
        rolled_back = [sp for sp in fake_db.savepoints if sp.rolled_back]
        assert len(committed) == 3, "Three good rows should commit via savepoint"
        assert len(rolled_back) == 2, "Two bad rows should rollback via savepoint"

        # --- At least one outer commit must have run for the 3 good rows.
        # BATCH_COMMIT_SIZE=50 so only the final commit runs for 5 items,
        # but the finalizer commit still happens before _finalize_task_status.
        assert fake_db.commits >= 1, "Expected at least one outer commit"

        # --- Session is always closed via ``finally``.
        assert fake_db.closed is True


@pytest.mark.unit
class TestRetryableExceptionSet:
    """The autoretry_for tuple must exclude programming errors."""

    def test_retry_set_contains_transient_exceptions_only(self) -> None:
        """Programming errors like ValueError must NOT be in the retry set."""
        import requests
        import sqlalchemy.exc

        from app.services.rate_limiter import CircuitBreakerError, RateLimitError

        retry = data_refresh._RETRY_EXCEPTIONS
        assert CircuitBreakerError in retry
        assert RateLimitError in retry
        assert requests.RequestException in retry
        assert sqlalchemy.exc.OperationalError in retry
        assert sqlalchemy.exc.InterfaceError in retry

        # Sanity-check: programming errors are NOT retryable.
        for exc in (ValueError, TypeError, KeyError, AttributeError):
            assert not issubclass(exc, retry), (
                f"{exc.__name__} should not be in the retry set"
            )

    def test_threshold_and_batch_size_are_module_constants(self) -> None:
        assert data_refresh.BATCH_COMMIT_SIZE == 50
        assert data_refresh.ERROR_THRESHOLD_RATIO == 0.1


@pytest.mark.unit
class TestFinalizeTaskStatus:
    """Direct tests for the threshold helper used by every refresh task."""

    def test_success_payload_when_no_errors(self) -> None:
        result = data_refresh._finalize_task_status(
            task_name="t",
            processed=10,
            errors=0,
            total=10,
            season="2024-25",
        )
        assert result["status"] == "success"
        assert result["error_rate"] == 0.0
        assert result["season"] == "2024-25"

    def test_degraded_payload_when_errors_under_threshold(self) -> None:
        result = data_refresh._finalize_task_status(
            task_name="t",
            processed=99,
            errors=1,
            total=100,
            season="2025-26",
        )
        assert result["status"] == "degraded"
        assert result["error_rate"] == pytest.approx(0.01)

    def test_raises_when_errors_exceed_threshold(self) -> None:
        with pytest.raises(RuntimeError, match=r"2/5 players failed"):
            data_refresh._finalize_task_status(
                task_name="t",
                processed=3,
                errors=2,
                total=5,
                season="2024-25",
            )

    def test_extra_fields_are_merged(self) -> None:
        result = data_refresh._finalize_task_status(
            task_name="t",
            processed=10,
            errors=0,
            total=10,
            season="2024-25",
            extra={"shot_zones_processed": 42},
        )
        assert result["shot_zones_processed"] == 42


@pytest.mark.unit
class TestDailyDataRefreshOrchestrator:
    """Verify the Celery chord orchestrator surfaces child failures.

    These tests stub out the whole pipeline: we monkeypatch ``chain`` so
    ``pipeline.apply_async()`` returns a fake ``AsyncResult`` whose ``.get()``
    either returns a happy payload or re-raises whatever the chord's child
    raised. That gives us end-to-end coverage of
    ``daily_data_refresh``'s error-propagation contract without needing a
    real broker.
    """

    def _patch_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
        result: Any,
    ) -> MagicMock:
        """Replace ``chain(...).apply_async()`` with a stub returning ``result``."""
        fake_signature = MagicMock()
        fake_signature.apply_async.return_value = result
        fake_chain = MagicMock(return_value=fake_signature)
        monkeypatch.setattr(data_refresh, "chain", fake_chain)
        return fake_signature

    def test_raises_when_child_task_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RuntimeError`` from a child (threshold exceeded) propagates."""

        class _FailingResult:
            id = "workflow-abc"

            def get(self, *_a: Any, **_kw: Any) -> dict[str, object]:
                # Mirrors the real contract: ``_finalize_task_status`` raises
                # ``RuntimeError`` when error_rate exceeds the threshold, and
                # Celery propagates it through ``.get(propagate=True)``.
                raise RuntimeError("2/5 players failed in refresh_impact_data")

        self._patch_pipeline(monkeypatch, _FailingResult())

        with pytest.raises(RuntimeError, match=r"players failed"):
            # ``.apply`` runs the task synchronously; ``task_eager_propagates``
            # is True via the autouse fixture so the inner raise surfaces here.
            data_refresh.daily_data_refresh.apply(args=["2024-25"]).get()

    def test_returns_success_payload_when_pipeline_completes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Happy path: ``.get()`` returns a dict, task returns success wrapper."""

        class _OkResult:
            id = "workflow-xyz"

            def get(self, *_a: Any, **_kw: Any) -> dict[str, object]:
                return {"status": "success", "season": "2024-25"}

        self._patch_pipeline(monkeypatch, _OkResult())

        payload = data_refresh.daily_data_refresh.apply(args=["2024-25"]).get()

        assert payload["status"] == "success"
        assert payload["workflow_id"] == "workflow-xyz"
        assert payload["season"] == "2024-25"
        assert payload["final"] == {"status": "success", "season": "2024-25"}

    def test_after_group_phase_marks_degraded_when_any_child_degraded(self) -> None:
        """The chord body rolls up child statuses into an overall tag."""
        group_results = [
            {"status": "success", "season": "2024-25"},
            {"status": "degraded", "season": "2024-25", "errors": 1},
            {"status": "success", "season": "2024-25"},
        ]
        out = data_refresh._after_group_phase.apply(
            args=[group_results, "2024-25"]
        ).get()
        assert out["status"] == "degraded"
        assert out["season"] == "2024-25"
        assert out["children"] == group_results

    def test_after_group_phase_success_when_all_children_succeed(self) -> None:
        group_results = [
            {"status": "success", "season": "2024-25"},
            {"status": "success", "season": "2024-25"},
        ]
        out = data_refresh._after_group_phase.apply(
            args=[group_results, "2024-25"]
        ).get()
        assert out["status"] == "success"
