"""Deployment-level configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment settings; runtime business configuration does not live here."""

    model_config = SettingsConfigDict(
        env_prefix="CLOTHES_MODEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    bind_host: str = "127.0.0.1"
    bind_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite+aiosqlite:///./data/clothes-model.db"
    sqlite_busy_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    storage_root: Path = Path("./data/storage")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_allowlist: list[str] = Field(default_factory=list)
    scheduler_enabled: bool = False
    instance_lock_path: Path = Path("./data/instance.lock")
    encryption_master_key_file: Path | None = None
    admin_session_cookie_secure: bool = True
    web_static_root: Path | None = None

    def safe_log_context(self) -> dict[str, str | int | bool]:
        return {
            "environment": self.environment,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "log_level": self.log_level,
            "scheduler_enabled": self.scheduler_enabled,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
