from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://localhost:5432/nba_stats"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Redis Cache TTL (Time To Live) Configuration
    cache_ttl_default: int = 86400  # 24 hours in seconds
    cache_ttl_players: int = 86400  # Player data TTL
    cache_ttl_tracking_stats: int = 86400  # Tracking stats TTL
    cache_ttl_game_possessions: int = 604800  # Game data TTL (7 days - historical)
    cache_enabled: bool = True  # Global cache enable/disable

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

    # Celery Configuration
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_time_limit: int = 3600  # 1 hour hard limit
    celery_task_soft_time_limit: int = 3300  # 55 min soft limit
    celery_schedule_hour: int = 6  # Hour to run daily refresh (UTC)
    celery_schedule_minute: int = 0  # Minute to run daily refresh

    # Observability
    # Sentry DSN is intentionally optional — when unset, ``init_sentry()`` is
    # a no-op so local development does not require a Sentry project.
    sentry_dsn: str | None = None
    sentry_env: str = "production"
    sentry_traces_sample_rate: float = 0.0  # Traces off by default; opt in via env.
    git_sha: str | None = None  # Populated by CI for Sentry release tagging.

    # Structured logging: JSON renderer in production, console renderer when
    # ``log_json=False`` (handy for local dev). Level applies to both the
    # stdlib root logger and structlog's default filtering logger.
    log_level: str = "INFO"
    log_json: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
