"""Конфигурация сервиса процессора платежей."""

from pathlib import Path

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parent.parent


class APIConfig(BaseModel):
    host: str
    port: int
    api_key: str
    reload: bool = False


class HeadersConfig(BaseModel):
    api_key: str = "X-API-Key"
    idempotency_key: str = "Idempotency-Key"


class DBConfig(BaseModel):
    host: str
    port: int
    user: str
    password: SecretStr
    database: str
    echo: bool = False
    expire_on_commit: bool = False
    autoflush: bool = False

    naming_convention: dict[str, str] = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }

    @property
    def async_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            host=self.host,
            port=self.port,
            database=self.database,
            username=self.user,
            password=self.password.get_secret_value(),
        )


class Settings(BaseSettings):
    api: APIConfig
    db: DBConfig
    headers: HeadersConfig = HeadersConfig()

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # type: ignore
