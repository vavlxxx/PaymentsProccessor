import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from src.schemas.base import BaseDTO
from src.utils.enums import OutboxStatus


class OutboxDTO(BaseDTO):
    id: int = Field(description="Уникальный идентификатор события outbox")
    event_id: uuid.UUID = Field(description="Уникальный UUID события")
    topic: str = Field(description="Очередь/топик назначения")
    event_type: str = Field(description="Тип события")
    payload: dict[str, Any] = Field(description="Тело события")
    status: OutboxStatus = Field(description="Статус отправки события")
    retry_count: int = Field(default=0, description="Количество попыток отправки")
    created_at: datetime = Field(description="Дата создания")
    updated_at: datetime = Field(description="Дата обновления")


class OutboxCreateDTO(BaseDTO):
    topic: str = Field(description="Очередь/топик назначения")
    event_type: str = Field(description="Тип события")
    payload: dict[str, Any] = Field(description="Тело события")
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="UUID события")
    status: OutboxStatus = Field(
        default=OutboxStatus.PENDING, description="Начальный статус"
    )
    retry_count: int = Field(default=0, description="Количество попыток")
