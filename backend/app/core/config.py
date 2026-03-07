from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"


settings = Settings()
