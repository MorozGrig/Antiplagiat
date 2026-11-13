"""Конфигурация приложения (Pydantic Settings v2).

Все параметры читаются из переменных окружения / .env файла.
Примеры имён переменных: POSTGRES_HOST, REDIS_URL, S3_ENDPOINT_URL,
ELASTICSEARCH_URL, MAX_FILE_SIZE и т.д.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки всего сервиса (FastAPI + Celery используют один и тот же класс)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Общее
    # ------------------------------------------------------------------ #
    app_name: str = "Author Materials Registry"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", description="development|staging|production")
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production", min_length=8)

    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])

    # ------------------------------------------------------------------ #
    # PostgreSQL
    #   - async_database_url используется FastAPI (asyncpg)
    #   - sync_database_url  используется Celery/worker-скриптами (psycopg2)
    # ------------------------------------------------------------------ #
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "registry"
    postgres_user: str = "registry"
    postgres_password: str = "registry"

    # Необязательные явные DSN — если заданы, имеют приоритет над *_host/_port/...
    database_url: Optional[str] = None       # async: postgresql+asyncpg://...
    database_sync_url: Optional[str] = None  # sync:  postgresql+psycopg2://...

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    # ------------------------------------------------------------------ #
    # Redis / Celery
    # ------------------------------------------------------------------ #
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""          # если пусто — берётся redis_url
    celery_result_backend: str = ""      # если пусто — берётся redis_url

    # ------------------------------------------------------------------ #
    # S3-совместимое хранилище (MinIO для локальной разработки)
    # ------------------------------------------------------------------ #
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket_files: str = "materials"            # исходники материалов
    s3_bucket_certificates: str = "certificates"  # PDF-свидетельства
    s3_presigned_url_expiry_seconds: int = 3600
    s3_use_ssl: bool = False

    # ------------------------------------------------------------------ #
    # Elasticsearch 8 + Apache Tika
    # ------------------------------------------------------------------ #
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_materials: str = "materials"
    elasticsearch_request_timeout: int = 30
    elasticsearch_verify_certs: bool = False

    tika_server_url: str = "http://localhost:9998/tika"

    # ------------------------------------------------------------------ #
    # Загрузка файлов / антиплагиат
    # ------------------------------------------------------------------ #
    max_file_size: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        description="Максимальный размер загружаемого файла в байтах (по умолчанию 10 МБ).",
    )
    allowed_mime_types: List[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "image/jpeg",
            "image/png",
            "video/mp4",
            "video/quicktime",
            "video/x-msvideo",
            "video/x-matroska",
        ],
        description="Разрешённые MIME-типы (статьи, изображения, видео, PDF).",
    )
    ocr_language: str = "rus+eng"
    similarity_threshold_percent: float = Field(
        default=70.0, ge=0.0, le=100.0,
        description="Порог схожести, ниже которого совпадения не считаются значимыми.",
    )
    minhash_num_perm: int = 128
    minhash_threshold: float = 0.5

    # ------------------------------------------------------------------ #
    # JWT (python-jose)
    # ------------------------------------------------------------------ #
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    log_level: str = "INFO"

    # ------------------------- computed -------------------------------- #
    @property
    def async_database_url(self) -> str:
        """DSN для FastAPI (SQLAlchemy + asyncpg)."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """DSN для Celery (SQLAlchemy + psycopg2)."""
        if self.database_sync_url:
            return self.database_sync_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        """Позволяет задать CORS_ORIGINS строкой через запятую."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def _split_mimes(cls, v):
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Кэшированный синглтон настроек (для Depends(...) в FastAPI)."""
    return Settings()


settings = get_settings()
