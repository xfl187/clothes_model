"""Deployment-level configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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
    storage_max_upload_bytes: int = Field(default=20_000_000, ge=1024)
    storage_reserve_bytes: int = Field(default=100_000_000, ge=0)
    upload_maintenance_interval_seconds: int = Field(default=300, ge=30, le=86400)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_allowlist: list[str] = Field(default_factory=list)
    scheduler_enabled: bool = False
    scheduler_poll_interval_seconds: float = Field(default=0.5, gt=0, le=60)
    scheduler_batch_size: int = Field(default=1, ge=1, le=16)
    scheduler_lease_minutes: int = Field(default=5, ge=1, le=60)
    instance_lock_path: Path = Path("./data/instance.lock")
    encryption_master_key_file: Path | None = None
    comfy_node_allowed_hosts: list[str] = Field(default_factory=list)
    admin_session_cookie_secure: bool = True
    admin_session_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    admin_login_max_failures: int = Field(default=5, ge=1, le=20)
    admin_login_window_seconds: int = Field(default=300, ge=30, le=3600)
    web_static_root: Path | None = None

    @model_validator(mode="after")
    def validate_security_policy(self) -> Settings:
        if self.environment == "production" and not self.admin_session_cookie_secure:
            raise ValueError("production requires secure Admin session cookies")
        return self

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
