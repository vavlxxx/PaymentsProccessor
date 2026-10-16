from pathlib import Path

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BASE_DIR = Path(__file__).resolve().parent.parent


class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8888
    api_key: str = "test-secret-api-key-12345"
    reload: bool = False


class HeadersConfig(BaseModel):
    api_key: str = "X-API-Key"
    idempotency_key: str = "Idempotency-Key"


class DBConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "payments"
    password: SecretStr = SecretStr("payments")
    database: str = "payments_db"
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


class RabbitConfig(BaseModel):
    host: str = "localhost"
    port: int = 5672
    user: str = "guest"
    password: SecretStr = SecretStr("guest")

    queue_name: str = "payments.new"
    retry_queue_name: str = "payments.retry"
    dlq_name: str = "payments.dlq"

    durable: bool = True
    max_retries: int = 3
    retry_ttl: int = 5000
    on_return_raises: bool = True

    @property
    def url(self) -> str:
        return f"amqp://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/"


class ProcessingConfig(BaseModel):
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 5.0
    success_rate: float = 0.9
    webhook_timeout: float = 5.0
    webhook_max_retries: int = 3
    webhook_retry_backoff: float = 1.0


class OutboxConfig(BaseModel):
    poll_interval: float = 1.0
    batch_size: int = 50


class Settings(BaseSettings):
    api: APIConfig = APIConfig()
    db: DBConfig = DBConfig()
    rabbit: RabbitConfig = RabbitConfig()
    headers: HeadersConfig = HeadersConfig()
    processing: ProcessingConfig = ProcessingConfig()
    outbox: OutboxConfig = OutboxConfig()

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # type: ignore
