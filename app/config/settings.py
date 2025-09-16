from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Database
    database_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Environment
    environment: str = "development"
    debug: bool = True

    # CORS
    allowed_hosts: List[str] = ["localhost", "127.0.0.1"]

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100
    # Threading (faltaban)
    max_workers: int = 2
    queue_check_interval: int = 5
    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_password: Optional[str] = None
    redis_db: int = 0

    # Monitoring
    queue_stats_update_interval: int = 2
    max_events_history: int = 1000
    worker_heartbeat_interval: int = 10

    @property
    def database_url_sync(self) -> str:
        """Convert async database URL to sync"""
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace(
                "postgresql+asyncpg://", "postgresql+psycopg2://"
            )
        elif self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg2://")
        else:
            return self.database_url

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
