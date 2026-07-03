from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Veriba Backend"
    debug: bool = False
    run_migrations_on_startup: bool = True
    seed_internal_admin_on_startup: bool = False
    version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    base_api_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:3000"
    patient_portal_base_url: str = "http://localhost:3000/upload"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "sqlite:///./veriba.db"
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: str = "local"
    storage_root: str = "/app/storage"
    public_storage_base_url: str = "http://localhost:8000/storage"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "veriba"
    minio_secure: bool = False
    resend_api_key: str | None = None
    resend_from_email: str = "hello@veriba.agence.studio"
    widget_rate_limit: str = "100/minute"
    patient_rate_limit: str = "10/minute"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024)
    max_web_bytes: int = Field(default=2 * 1024 * 1024)
    max_web_width: int = 2000
    celery_eager: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
