from pydantic_settings import BaseSettings
from typing import List


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
