"""Shared utilities for custom metrics computation.

Provides normalization, percentile ranking, position mapping, and
safe type conversion helpers used across all custom metric services.
"""

from decimal import Decimal


def normalize_to_0_100(value: float, min_val: float, max_val: float) -> float:
    """Linearly map a value from [min_val, max_val] to [0, 100], clamped."""
    if max_val == min_val:
        return 50.0
    score = (value - min_val) / (max_val - min_val) * 100
    return max(0.0, min(100.0, score))


def percentile_rank(value: float, all_values: list[float]) -> float:
    """Compute the percentile rank (0-100) of a value within a distribution."""
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if v < value)
    return (below / len(all_values)) * 100


def safe_float(value, default: float = 0.0) -> float:
    """Convert Decimal/None to float safely."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division, returns default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def to_decimal(value: float, places: str = "0.01") -> Decimal:
    """Convert float to quantized Decimal for DB storage."""
    return Decimal(str(value)).quantize(Decimal(places))


# Position classification for defensive switchability
POSITION_BUCKETS = {
    "PG": "G",
    "SG": "G",
    "G": "G",
    "SF": "W",
    "G-F": "W",
    "F-G": "W",
    "PF": "F",
    "F": "F",
    "C": "C",
    "F-C": "C",
    "C-F": "C",
}

# League average FG% by position bucket (approximate 2024-25 values)
POSITION_LEAGUE_AVG_FG = {
    "G": 0.445,
    "W": 0.460,
    "F": 0.480,
    "C": 0.530,
}


def map_position_to_bucket(pos: str | None) -> str:
    """Map NBA API position string to a 4-bucket classification."""
    if not pos:
        return "W"
    return POSITION_BUCKETS.get(pos.upper().strip(), "W")
