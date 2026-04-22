"""Unit tests for the NBA data service module.

This module tests:
- Cache hit returns cached data without API call
- Cache miss calls API and caches result
- bypass_cache=True skips cache
- Circuit breaker integration
- Error handling for rate limits and server errors
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.nba_data import (
    NBADataService,
    PlayerTrackingData,
)
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
)


class TestNBADataServiceCaching:
    """Tests for NBADataService caching behavior."""

    @pytest.fixture
    def mock_service(self, mock_settings):
        """Provide NBADataService with mocked dependencies."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session") as mock_session:
                mock_session.return_value = MagicMock()
                service = NBADataService(base_delay=0.01)
                return service

    def test_cache_hit_returns_cached_data(self, mock_service, sample_player_data):
        """Verify cache hit returns cached data without API call."""
        with patch("app.services.nba_data.redis_cache") as mock_cache:
            mock_cache.get.return_value = sample_player_data

            result = mock_service.get_all_players(season="2024-25")

            assert result == sample_player_data
            mock_cache.get.assert_called_once()
            # Should not make any API calls

    def test_cache_miss_calls_api(self, mock_service, mock_settings):
        """Verify cache miss triggers API call."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.redis_cache") as mock_cache:
                with patch("app.services.nba_data.nba_api_circuit_breaker") as mock_cb:
                    mock_cache.get.return_value = None  # Cache miss
                    mock_cb.can_execute.return_value = True

                    # Mock the API endpoint
                    mock_endpoint = MagicMock()
                    mock_endpoint.get_normalized_dict.return_value = {
                        "CommonAllPlayers": [{"PERSON_ID": 1}]
                    }

                    with patch.object(
                        mock_service, "_request_with_retry", return_value=mock_endpoint
                    ) as mock_request:
                        result = mock_service.get_all_players(season="2024-25")

                        mock_request.assert_called_once()
                        mock_cache.set.assert_called_once()
                        assert result == [{"PERSON_ID": 1}]

    def test_bypass_cache_skips_cache_lookup(self, mock_settings, sample_player_data):
        """Verify bypass_cache=True skips cache and calls API."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session") as mock_session:
                mock_session.return_value = MagicMock()
                service = NBADataService(bypass_cache=True, base_delay=0.01)

                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True

                        mock_endpoint = MagicMock()
                        mock_endpoint.get_normalized_dict.return_value = {
                            "CommonAllPlayers": sample_player_data
                        }

                        with patch.object(
                            service,
                            "_request_with_retry",
                            return_value=mock_endpoint,
                        ):
                            result = service.get_all_players(season="2024-25")

                            # Cache get should NOT be called when bypassing
                            mock_cache.get.assert_not_called()
                            # But result should still be cached
                            mock_cache.set.assert_called_once()
                            assert result == sample_player_data


class TestNBADataServiceCircuitBreaker:
    """Tests for circuit breaker integration."""

    def test_raises_circuit_breaker_error_when_open(self, mock_settings):
        """Verify CircuitBreakerError is raised when circuit is open."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                service = NBADataService(base_delay=0.01)

                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None  # Force API call

                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = False
                        mock_cb.recovery_timeout = 60.0
                        mock_cb._last_failure_time = None

                        with pytest.raises(CircuitBreakerError):
                            service.get_all_players(season="2024-25")

    def test_records_success_after_successful_api_call(self, mock_settings):
        """Verify success is recorded to circuit breaker."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None

                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True

                        service = NBADataService(max_retries=0, base_delay=0.01)

                        # Mock successful endpoint call
                        with patch(
                            "app.services.nba_data.CommonAllPlayers"
                        ) as mock_endpoint_class:
                            mock_endpoint = MagicMock()
                            mock_endpoint.get_normalized_dict.return_value = {
                                "CommonAllPlayers": []
                            }
                            mock_endpoint_class.return_value = mock_endpoint

                            with patch("time.sleep"):
                                service.get_all_players(season="2024-25")

                            mock_cb.record_success.assert_called()


class TestNBADataServiceRetryBehavior:
    """Tests for retry behavior on API failures."""

    def test_retries_on_rate_limit_error(self, mock_settings):
        """Verify service retries on rate limit errors."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None

                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True

                        service = NBADataService(max_retries=2, base_delay=0.01)

                        call_count = 0

                        def mock_endpoint_call(*args, **kwargs):
                            nonlocal call_count
                            call_count += 1
                            if call_count < 3:
                                raise Exception("429 Too Many Requests")
                            mock_resp = MagicMock()
                            mock_resp.get_normalized_dict.return_value = {
                                "CommonAllPlayers": []
                            }
                            return mock_resp

                        with patch(
                            "app.services.nba_data.CommonAllPlayers",
                            side_effect=mock_endpoint_call,
                        ):
                            with patch("time.sleep"):
                                result = service.get_all_players(season="2024-25")

                        assert call_count == 3
                        assert result == []

    def test_raises_rate_limit_error_after_max_retries(self, mock_settings):
        """Verify RateLimitError is raised after max retries exceeded."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None

                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True

                        service = NBADataService(max_retries=2, base_delay=0.01)

                        with patch(
                            "app.services.nba_data.CommonAllPlayers",
                            side_effect=Exception("429 Too Many Requests"),
                        ):
                            with patch("time.sleep"):
                                with pytest.raises(RateLimitError):
                                    service.get_all_players(season="2024-25")

    def test_non_retryable_error_raises_immediately(self, mock_settings):
        """Verify non-retryable errors are raised without retry."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None

                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True

                        service = NBADataService(max_retries=5, base_delay=0.01)

                        call_count = 0

                        def mock_error(*args, **kwargs):
                            nonlocal call_count
                            call_count += 1
                            raise ValueError("Invalid parameter")

                        with patch(
                            "app.services.nba_data.CommonAllPlayers",
                            side_effect=mock_error,
                        ):
                            with patch("time.sleep"):
                                with pytest.raises(ValueError):
                                    service.get_all_players(season="2024-25")

                        # Should only be called once (no retries)
                        assert call_count == 1


class TestNBADataServiceEndpoints:
    """Tests for specific NBA API endpoint methods."""

    @pytest.fixture
    def service_with_mocked_api(self, mock_settings):
        """Provide service with mocked API calls."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                with patch("app.services.nba_data.redis_cache") as mock_cache:
                    mock_cache.get.return_value = None
                    with patch(
                        "app.services.nba_data.nba_api_circuit_breaker"
                    ) as mock_cb:
                        mock_cb.can_execute.return_value = True
                        service = NBADataService(max_retries=0, base_delay=0.01)
                        yield service, mock_cache

    def test_get_traditional_stats_caches_result(
        self, service_with_mocked_api, sample_traditional_stats
    ):
        """Verify get_traditional_stats caches the result."""
        service, mock_cache = service_with_mocked_api

        mock_endpoint = MagicMock()
        mock_endpoint.get_normalized_dict.return_value = {
            "LeagueDashPlayerStats": sample_traditional_stats
        }

        with patch(
            "app.services.nba_data.LeagueDashPlayerStats",
            return_value=mock_endpoint,
        ):
            with patch("time.sleep"):
                result = service.get_traditional_stats(season="2024-25")

        assert result == sample_traditional_stats
        mock_cache.set.assert_called_once()
        # Verify cache key contains the right prefix
        call_args = mock_cache.set.call_args
        assert "nba:traditional_stats" in call_args[0][0]

    def test_get_touch_stats_caches_result(
        self, service_with_mocked_api, sample_tracking_stats
    ):
        """Verify get_touch_stats caches the result."""
        service, mock_cache = service_with_mocked_api

        mock_endpoint = MagicMock()
        mock_endpoint.get_normalized_dict.return_value = {
            "LeagueDashPtStats": sample_tracking_stats
        }

        with patch(
            "app.services.nba_data.LeagueDashPtStats",
            return_value=mock_endpoint,
        ):
            with patch("time.sleep"):
                result = service.get_touch_stats(season="2024-25")

        assert result == sample_tracking_stats
        mock_cache.set.assert_called_once()

    def test_get_hustle_stats_caches_result(self, service_with_mocked_api):
        """Verify get_hustle_stats caches the result."""
        service, mock_cache = service_with_mocked_api

        hustle_data = [
            {
                "PLAYER_ID": 1,
                "DEFLECTIONS": 50,
                "CONTESTED_SHOTS_2PT": 100,
                "CONTESTED_SHOTS_3PT": 30,
            }
        ]

        mock_endpoint = MagicMock()
        mock_endpoint.get_normalized_dict.return_value = {
            "HustleStatsPlayer": hustle_data
        }

        with patch(
            "app.services.nba_data.LeagueHustleStatsPlayer",
            return_value=mock_endpoint,
        ):
            with patch("time.sleep"):
                result = service.get_hustle_stats(season="2024-25")

        assert result == hustle_data
        mock_cache.set.assert_called_once()

    def test_get_defensive_stats_caches_result(self, service_with_mocked_api):
        """Verify get_defensive_stats caches the result."""
        service, mock_cache = service_with_mocked_api

        defensive_data = [
            {
                "CLOSE_DEF_PERSON_ID": 1,
                "D_FG_PCT": 0.45,
            }
        ]

        mock_endpoint = MagicMock()
        mock_endpoint.get_normalized_dict.return_value = {
            "LeagueDashPTDefend": defensive_data
        }

        with patch(
            "app.services.nba_data.LeagueDashPtDefend",
            return_value=mock_endpoint,
        ):
            with patch("time.sleep"):
                result = service.get_defensive_stats(season="2024-25")

        assert result == defensive_data
        mock_cache.set.assert_called_once()


class TestFetchAllTrackingData:
    """Tests for the combined tracking data fetch."""

    def test_combines_data_from_multiple_endpoints(self, mock_settings):
        """Verify fetch_all_tracking_data combines data from all endpoints."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                service = NBADataService(base_delay=0.01)

                traditional = [
                    {
                        "PLAYER_ID": 1,
                        "PLAYER_NAME": "Test Player",
                        "TEAM_ABBREVIATION": "TST",
                        "PTS": 500,
                        "AST": 100,
                        "TOV": 50,
                        "FTA": 75,
                        "MIN": 1000.0,
                    }
                ]
                touches = [
                    {
                        "PLAYER_ID": 1,
                        "TOUCHES": 100,
                        "FRONT_CT_TOUCHES": 80,
                        "TIME_OF_POSS": 5.5,
                        "AVG_SEC_PER_TOUCH": 2.1,
                        "AVG_DRIB_PER_TOUCH": 1.5,
                        "PTS_PER_TOUCH": 0.4,
                    }
                ]
                hustle = [
                    {
                        "PLAYER_ID": 1,
                        "DEFLECTIONS": 50,
                        "CONTESTED_SHOTS_2PT": 100,
                        "CONTESTED_SHOTS_3PT": 30,
                        "CHARGES_DRAWN": 5,
                        "LOOSE_BALLS_RECOVERED": 20,
                    }
                ]
                defense = [
                    {
                        "CLOSE_DEF_PERSON_ID": 1,
                        "D_FG_PCT": 0.45,
                    }
                ]

                with patch.object(
                    service, "get_traditional_stats", return_value=traditional
                ):
                    with patch.object(
                        service, "get_touch_stats", return_value=touches
                    ):
                        with patch.object(
                            service, "get_hustle_stats", return_value=hustle
                        ):
                            with patch.object(
                                service, "get_defensive_stats", return_value=defense
                            ):
                                result = service.fetch_all_tracking_data(
                                    season="2024-25"
                                )

                assert 1 in result
                player_data = result[1]
                assert isinstance(player_data, PlayerTrackingData)
                assert player_data.player_name == "Test Player"
                assert player_data.touches == 100
                assert player_data.deflections == 50
                assert player_data.points == 500

    def test_skips_players_without_touch_data(self, mock_settings):
        """Verify players without touch data are excluded."""
        with patch("app.services.nba_data.settings", mock_settings):
            with patch("app.services.nba_data.get_nba_session"):
                service = NBADataService(base_delay=0.01)

                traditional = [
                    {
                        "PLAYER_ID": 1,
                        "PLAYER_NAME": "Player With Touches",
                        "TEAM_ABBREVIATION": "TST",
                        "PTS": 500,
                        "AST": 100,
                        "TOV": 50,
                        "FTA": 75,
                        "MIN": 1000.0,
                    },
                    {
                        "PLAYER_ID": 2,
                        "PLAYER_NAME": "Player Without Touches",
                        "TEAM_ABBREVIATION": "TST",
                        "PTS": 10,
                        "AST": 5,
                        "TOV": 2,
                        "FTA": 3,
                        "MIN": 50.0,
                    },
                ]
                touches = [
                    {
                        "PLAYER_ID": 1,
                        "TOUCHES": 100,
                        "FRONT_CT_TOUCHES": 80,
                        "TIME_OF_POSS": 5.5,
                        "AVG_SEC_PER_TOUCH": 2.1,
                        "AVG_DRIB_PER_TOUCH": 1.5,
                        "PTS_PER_TOUCH": 0.4,
                    },
                    # Player 2 has no touches
                    {
                        "PLAYER_ID": 2,
                        "TOUCHES": 0,  # No touches
                    },
                ]

                with patch.object(
                    service, "get_traditional_stats", return_value=traditional
                ):
                    with patch.object(
                        service, "get_touch_stats", return_value=touches
                    ):
                        with patch.object(service, "get_hustle_stats", return_value=[]):
                            with patch.object(
                                service, "get_defensive_stats", return_value=[]
                            ):
                                result = service.fetch_all_tracking_data(
                                    season="2024-25"
                                )

                # Only player 1 should be included
                assert 1 in result
                assert 2 not in result


class TestPlayerTrackingDataClass:
    """Tests for PlayerTrackingData dataclass."""

    def test_dataclass_fields(self):
        """Verify all expected fields are present."""
        player = PlayerTrackingData(
            player_id=1,
            player_name="Test Player",
            team_abbreviation="TST",
            games_played=70,
            touches=100,
            front_court_touches=80,
            paint_touches=10,
            post_touches=5,
            elbow_touches=3,
            time_of_possession=Decimal("5.5"),
            avg_seconds_per_touch=Decimal("2.1"),
            avg_dribbles_per_touch=Decimal("1.5"),
            points_per_touch=Decimal("0.4"),
            deflections=50,
            contested_shots_2pt=100,
            contested_shots_3pt=30,
            charges_drawn=5,
            loose_balls_recovered=20,
            off_loose_balls_recovered=8,
            def_loose_balls_recovered=12,
            pct_loose_balls_off=Decimal("0.4"),
            pct_loose_balls_def=Decimal("0.6"),
            box_outs=40,
            box_outs_off=10,
            box_outs_def=30,
            box_out_player_team_rebs=25,
            box_out_player_rebs=18,
            pct_box_outs_off=Decimal("0.25"),
            pct_box_outs_def=Decimal("0.75"),
            pct_box_outs_team_reb=Decimal("0.6"),
            pct_box_outs_reb=Decimal("0.45"),
            screen_assists=15,
            screen_assist_pts=40,
            points=500,
            assists=100,
            turnovers=50,
            steals=60,
            blocks=40,
            offensive_rebounds=70,
            defensive_rebounds=200,
            rebounds=270,
            fgm=180,
            fga=400,
            fg3m=50,
            fg3a=140,
            ftm=90,
            fta=75,
            minutes=Decimal("1000.0"),
            plus_minus=120,
        )

        assert player.player_id == 1
        assert player.player_name == "Test Player"
        assert player.touches == 100
        assert player.points_per_touch == Decimal("0.4")
        assert player.paint_touches == 10
        assert player.box_out_player_rebs == 18
