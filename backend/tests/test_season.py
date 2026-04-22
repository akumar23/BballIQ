"""Unit tests for :mod:`app.core.season`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest

from app.core.season import current_season_dep, get_current_season, season_for_date


@pytest.mark.unit
class TestSeasonForDate:
    """Verify the deterministic pure function."""

    @pytest.mark.parametrize(
        ("today", "expected"),
        [
            # --- Before Oct 1: returns the prior season (ends in June) ---
            (date(2025, 1, 1), "2024-25"),
            (date(2025, 4, 15), "2024-25"),
            (date(2025, 6, 30), "2024-25"),
            # --- Offseason (Jul-Sep): still prior season ---
            (date(2025, 7, 1), "2024-25"),
            (date(2025, 9, 30), "2024-25"),
            # --- On Oct 1 exactly: flips to new season ---
            (date(2025, 10, 1), "2025-26"),
            # --- After Oct 1: new season ---
            (date(2025, 10, 15), "2025-26"),
            (date(2025, 12, 31), "2025-26"),
            # --- Year boundary edges ---
            (date(2026, 1, 1), "2025-26"),
            (date(2025, 9, 30), "2024-25"),
        ],
    )
    def test_season_for_specific_dates(self, today: date, expected: str) -> None:
        assert season_for_date(today) == expected

    def test_returns_yyyy_yy_format(self) -> None:
        """Ensure the output always matches the NBA convention."""
        for year in (2000, 2025, 2099):
            for sample in (date(year, 3, 1), date(year, 11, 1)):
                season = season_for_date(sample)
                assert len(season) == 7, season
                assert season[4] == "-", season

    def test_turn_of_century(self) -> None:
        """2099-10-15 should roll into ``2099-00`` (last two digits of 2100)."""
        assert season_for_date(date(2099, 10, 15)) == "2099-00"

    def test_september_30_is_prior_season(self) -> None:
        assert season_for_date(date(2024, 9, 30)) == "2023-24"

    def test_october_1_is_new_season(self) -> None:
        assert season_for_date(date(2024, 10, 1)) == "2024-25"


@pytest.mark.unit
class TestGetCurrentSeason:
    """Verify the wall-clock variant uses UTC and delegates correctly."""

    def test_uses_utc_now(self) -> None:
        """``get_current_season`` reads ``datetime.now(timezone.utc)``."""
        fake_now = datetime(2025, 11, 15, 3, 0, 0, tzinfo=UTC)
        with patch("app.core.season.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert get_current_season() == "2025-26"
            mock_dt.now.assert_called_once_with(UTC)

    def test_matches_season_for_date(self) -> None:
        fake_now = datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)
        with patch("app.core.season.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert get_current_season() == season_for_date(fake_now.date())


@pytest.mark.unit
class TestCurrentSeasonDep:
    """Verify the FastAPI dependency wrapper just returns the current season."""

    def test_returns_current_season(self) -> None:
        fake_now = datetime(2025, 10, 1, 0, 0, 0, tzinfo=UTC)
        with patch("app.core.season.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            assert current_season_dep() == "2025-26"
