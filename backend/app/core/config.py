from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://localhost:5432/nba_stats"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # NBA API
    nba_api_cache_dir: str = "./data/nba_api_cache"

    # Metric calculation
    min_touches_for_metric: int = 50
    min_minutes_for_metric: int = 100

    # Rate Limiting Configuration
    nba_api_base_delay: float = 0.6  # Base delay between requests in seconds
    nba_api_max_retries: int = 5  # Maximum retry attempts
    nba_api_backoff_base: float = 2.0  # Exponential backoff base multiplier
    nba_api_backoff_max: float = 60.0  # Maximum backoff delay in seconds
    nba_api_jitter_max: float = 0.5  # Maximum jitter to add (0-1 range)
    nba_api_timeout: int = 30  # Request timeout in seconds

    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = 5  # Failures before opening circuit
    circuit_breaker_recovery_timeout: float = 60.0  # Seconds before attempting recovery
    circuit_breaker_half_open_max_calls: int = 3  # Calls allowed in half-open state

    class Config:
        env_file = ".env"


settings = Settings()
