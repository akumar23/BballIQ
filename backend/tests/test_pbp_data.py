"""Unit tests for the PBP data service module.

This module tests:
- Cache hit/miss behavior
- bypass_cache parameter functionality
- Circuit breaker integration
- Retry behavior on failures
- Multiple game fetching with error recovery
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.pbp_data import (
    PBPStatsService,
    PossessionStats,
    pbp_stats_circuit_breaker,
    pbp_stats_service,
)
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
)


class TestPBPStatsServiceCaching:
    """Tests for PBPStatsService caching behavior."""

    @pytest.fixture
    def mock_service(self, mock_settings):
        """Provide PBPStatsService with mocked dependencies."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)
            return service

    def test_cache_hit_returns_cached_data(self, mock_service):
        """Verify cache hit returns cached data without API call."""
        cached_data = {"games": [{"game_id": "0022400001"}]}

        with patch("app.services.pbp_data.redis_cache") as mock_cache:
            mock_cache.get.return_value = cached_data

            result = mock_service.get_season_totals(
                season="2024-25", season_type="Regular Season"
            )

            assert result == cached_data
            mock_cache.get.assert_called_once()

    def test_cache_miss_calls_api(self, mock_service, mock_settings):
        """Verify cache miss triggers API call."""
        with patch("app.services.pbp_data.settings", mock_settings):
            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    mock_client = MagicMock()
                    mock_season = MagicMock()
                    mock_season.games.items = [{"game_id": "0022400001"}]
                    mock_client.Season.return_value = mock_season

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            result = mock_service.get_season_totals(
                                season="2024-25", season_type="Regular Season"
                            )

                    assert "games" in result
                    mock_cache.set.assert_called_once()

    def test_bypass_cache_skips_cache_lookup(self, mock_settings):
        """Verify bypass_cache=True skips cache and calls API."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(bypass_cache=True, base_delay=0.01)

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = {"cached": True}

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    mock_client = MagicMock()
                    mock_season = MagicMock()
                    mock_season.games.items = []
                    mock_client.Season.return_value = mock_season

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            service.get_season_totals(
                                season="2024-25", season_type="Regular Season"
                            )

                    # Cache get should NOT be called when bypassing
                    mock_cache.get.assert_not_called()
                    # But result should still be cached
                    mock_cache.set.assert_called_once()


class TestPBPStatsServiceCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_raises_circuit_breaker_error_when_open(self, mock_settings):
        """Verify CircuitBreakerError is raised when circuit is open."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = False
                    mock_cb.recovery_timeout = 60.0
                    mock_cb._last_failure_time = None

                    with pytest.raises(CircuitBreakerError):
                        service.get_season_totals(
                            season="2024-25", season_type="Regular Season"
                        )

    def test_records_success_after_successful_api_call(self, mock_settings):
        """Verify success is recorded to circuit breaker."""
        with patch("app.services.pbp_data.settings", mock_settings):
            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    service = PBPStatsService(max_retries=0, base_delay=0.01)

                    mock_client = MagicMock()
                    mock_season = MagicMock()
                    mock_season.games.items = []
                    mock_client.Season.return_value = mock_season

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            service.get_season_totals(
                                season="2024-25", season_type="Regular Season"
                            )

                    mock_cb.record_success.assert_called()


class TestPBPStatsServiceRetryBehavior:
    """Tests for retry behavior on API failures."""

    def test_retries_on_rate_limit_error(self, mock_settings):
        """Verify service retries on rate limit errors."""
        with patch("app.services.pbp_data.settings", mock_settings):
            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    service = PBPStatsService(max_retries=2, base_delay=0.01)

                    call_count = 0

                    def mock_client_call(*args, **kwargs):
                        nonlocal call_count
                        call_count += 1
                        if call_count < 3:
                            raise Exception("429 Too Many Requests")
                        mock_season = MagicMock()
                        mock_season.games.items = []
                        return mock_season

                    mock_client = MagicMock()
                    mock_client.Season.side_effect = mock_client_call

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            result = service.get_season_totals(
                                season="2024-25", season_type="Regular Season"
                            )

                    assert call_count == 3
                    assert "games" in result

    def test_raises_rate_limit_error_after_max_retries(self, mock_settings):
        """Verify RateLimitError is raised after max retries exceeded."""
        with patch("app.services.pbp_data.settings", mock_settings):
            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    service = PBPStatsService(max_retries=2, base_delay=0.01)

                    mock_client = MagicMock()
                    mock_client.Season.side_effect = Exception("429 Too Many Requests")

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            with pytest.raises(RateLimitError):
                                service.get_season_totals(
                                    season="2024-25", season_type="Regular Season"
                                )

    def test_non_retryable_error_returns_empty_without_retry(self, mock_settings):
        """Verify non-retryable errors return empty result without retry."""
        with patch("app.services.pbp_data.settings", mock_settings):
            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    service = PBPStatsService(max_retries=5, base_delay=0.01)

                    call_count = 0

                    def mock_error(*args, **kwargs):
                        nonlocal call_count
                        call_count += 1
                        raise ValueError("Invalid parameter")

                    mock_client = MagicMock()
                    mock_client.Season.side_effect = mock_error

                    with patch("app.services.pbp_data.Client", return_value=mock_client):
                        with patch("time.sleep"):
                            # Code catches exceptions and returns empty result
                            result = service.get_season_totals(
                                season="2024-25", season_type="Regular Season"
                            )

                    # Should only be called once (no retries for non-retryable error)
                    assert call_count == 1
                    # Returns empty games list on error
                    assert result == {"games": []}


class TestGetGamePossessions:
    """Tests for get_game_possessions method."""

    def test_cache_hit_returns_cached_possessions(self, mock_settings):
        """Verify cache hit returns cached possessions."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)
            cached_possessions = [{"possession_id": 1}, {"possession_id": 2}]

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = cached_possessions

                result = service.get_game_possessions(game_id="0022400001")

                assert result == cached_possessions
                mock_cache.get.assert_called_once()

    def test_cache_miss_fetches_from_api(self, mock_settings):
        """Verify cache miss triggers API fetch."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    mock_game = MagicMock()
                    mock_game.possessions.items = [{"id": 1}]
                    mock_client = MagicMock()
                    mock_client.Game.return_value = mock_game

                    with patch.object(service, "get_client", return_value=mock_client):
                        with patch("time.sleep"):
                            result = service.get_game_possessions(game_id="0022400001")

                    assert result == [{"id": 1}]
                    mock_cache.set.assert_called_once()

    def test_bypass_cache_skips_lookup(self, mock_settings):
        """Verify bypass_cache skips cache lookup."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(bypass_cache=True, base_delay=0.01)

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = [{"cached": True}]

                with patch(
                    "app.services.pbp_data.pbp_stats_circuit_breaker"
                ) as mock_cb:
                    mock_cb.can_execute.return_value = True

                    mock_game = MagicMock()
                    mock_game.possessions.items = [{"fresh": True}]
                    mock_client = MagicMock()
                    mock_client.Game.return_value = mock_game

                    with patch.object(service, "get_client", return_value=mock_client):
                        with patch("time.sleep"):
                            result = service.get_game_possessions(game_id="0022400001")

                    mock_cache.get.assert_not_called()
                    assert result == [{"fresh": True}]


class TestGetMultipleGamePossessions:
    """Tests for batch game possession fetching."""

    def test_fetches_multiple_games(self, mock_settings):
        """Verify multiple games can be fetched."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            game_ids = ["0022400001", "0022400002", "0022400003"]

            with patch.object(service, "get_game_possessions") as mock_get:
                mock_get.side_effect = [
                    [{"id": 1}],
                    [{"id": 2}],
                    [{"id": 3}],
                ]

                result = service.get_multiple_game_possessions(game_ids)

                assert len(result) == 3
                assert "0022400001" in result
                assert "0022400002" in result
                assert "0022400003" in result

    def test_reports_progress(self, mock_settings):
        """Verify progress callback is called."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            game_ids = ["0022400001", "0022400002"]
            progress_log = []

            def on_progress(completed, total, game_id):
                progress_log.append((completed, total, game_id))

            with patch.object(service, "get_game_possessions", return_value=[]):
                service.get_multiple_game_possessions(
                    game_ids, on_progress=on_progress
                )

            assert len(progress_log) == 2
            assert progress_log[0] == (1, 2, "0022400001")
            assert progress_log[1] == (2, 2, "0022400002")

    def test_handles_rate_limit_error(self, mock_settings):
        """Verify rate limit errors are handled gracefully."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            game_ids = ["0022400001", "0022400002", "0022400003"]

            call_count = 0

            def mock_get(game_id):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise RateLimitError("Rate limited", retry_after=0.1)
                return [{"game_id": game_id}]

            with patch.object(service, "get_game_possessions", side_effect=mock_get):
                with patch("time.sleep"):
                    result = service.get_multiple_game_possessions(game_ids)

            # Should have fetched games 1 and 3, game 2 failed
            assert "0022400001" in result
            assert "0022400002" not in result
            assert "0022400003" in result

    def test_handles_circuit_breaker_error(self, mock_settings):
        """Verify circuit breaker errors trigger wait and retry."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            game_ids = ["0022400001", "0022400002"]

            call_count = 0

            def mock_get(game_id):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise CircuitBreakerError("Circuit open", recovery_time=0.05)
                return [{"game_id": game_id}]

            with patch.object(service, "get_game_possessions", side_effect=mock_get):
                with patch("time.sleep"):
                    result = service.get_multiple_game_possessions(game_ids)

            # First game should have been retried after recovery
            assert call_count >= 2

    def test_handles_generic_errors(self, mock_settings):
        """Verify generic errors don't stop batch processing."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            game_ids = ["0022400001", "0022400002", "0022400003"]

            def mock_get(game_id):
                if game_id == "0022400002":
                    raise Exception("Unknown error")
                return [{"game_id": game_id}]

            with patch.object(service, "get_game_possessions", side_effect=mock_get):
                result = service.get_multiple_game_possessions(game_ids)

            # Should still get games 1 and 3
            assert "0022400001" in result
            assert "0022400002" not in result
            assert "0022400003" in result


class TestPBPStatsServiceHelpers:
    """Tests for helper methods."""

    def test_get_cache_key_format(self, mock_settings):
        """Verify cache key format is correct."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService()

            from app.services.redis_cache import CacheKeyPrefix

            key = service._get_cache_key(
                CacheKeyPrefix.PBP_SEASON_TOTALS, "2024-25", "regular_season"
            )

            assert key == "pbp:season_totals:2024-25:regular_season"

    def test_get_circuit_recovery_time_no_failure(self, mock_settings):
        """Verify recovery time is 0 when no failures recorded."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService()

            with patch(
                "app.services.pbp_data.pbp_stats_circuit_breaker"
            ) as mock_cb:
                mock_cb._last_failure_time = None

                recovery_time = service._get_circuit_recovery_time()

                assert recovery_time == 0

    def test_get_client_returns_client_instance(self, mock_settings):
        """Verify get_client returns a configured Client instance."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService()

            with patch("app.services.pbp_data.Client") as mock_client_class:
                mock_client_class.return_value = MagicMock()

                client = service.get_client()

                mock_client_class.assert_called_once()
                assert client is not None


class TestPossessionStatsDataclass:
    """Tests for PossessionStats dataclass."""

    def test_dataclass_fields(self):
        """Verify all expected fields are present."""
        from decimal import Decimal

        stats = PossessionStats(
            player_id=1,
            player_name="Test Player",
            total_possessions=100,
            points_per_possession=Decimal("1.05"),
            turnover_rate=Decimal("0.15"),
            assist_rate=Decimal("0.25"),
            isolation_poss=20,
            pnr_ball_handler_poss=30,
            pnr_roll_man_poss=10,
            post_up_poss=15,
            spot_up_poss=25,
            transition_poss=12,
            cut_poss=8,
        )

        assert stats.player_id == 1
        assert stats.player_name == "Test Player"
        assert stats.total_possessions == 100
        assert stats.points_per_possession == Decimal("1.05")
        assert stats.isolation_poss == 20


class TestCacheKeyGeneration:
    """Tests for cache key generation with different parameters."""

    def test_season_type_normalization(self, mock_settings):
        """Verify season type is normalized in cache key."""
        with patch("app.services.pbp_data.settings", mock_settings):
            service = PBPStatsService(base_delay=0.01)

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = {"data": "cached"}

                # Regular Season
                service.get_season_totals(
                    season="2024-25", season_type="Regular Season"
                )

                call_args = mock_cache.get.call_args[0][0]
                assert "regular_season" in call_args

            with patch("app.services.pbp_data.redis_cache") as mock_cache:
                mock_cache.get.return_value = {"data": "cached"}

                # Playoffs
                service.get_season_totals(season="2024-25", season_type="Playoffs")

                call_args = mock_cache.get.call_args[0][0]
                assert "playoffs" in call_args
