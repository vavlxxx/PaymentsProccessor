import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import AliasChoices, Field

from src.schemas.base import BaseDTO
from src.utils.enums import Currency, PaymentStatus


class PaymentDTO(BaseDTO):
    payment_id: uuid.UUID = Field(
        validation_alias=AliasChoices("payment_id", "id"),
        description="Уникальный идентификатор платежа",
    )
    amount: Decimal = Field(description="Сумма платежа")
    currency: Currency = Field(description="Валюта платежа")
    description: str = Field(description="Описание платежа")
    payment_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payment_metadata", "metadata"),
        description="Дополнительные метаданные платежа",
    )
    status: PaymentStatus = Field(description="Статус платежа")
    idempotency_key: str = Field(description="Уникальный ключ идемпотентности")
    webhook_url: str = Field(description="URL для webhook уведомления")
    created_at: datetime = Field(description="Дата и время создания")
    processed_at: datetime | None = Field(
        default=None, description="Дата и время обработки"
    )

    @property
    def id(self) -> uuid.UUID:
        return self.payment_id


class PaymentAddDTO(BaseDTO):
    payment_id: uuid.UUID | None = Field(
        default=None, description="Уникальный идентификатор платежа"
    )
    amount: Decimal = Field(gt=0, description="Сумма платежа (больше нуля)")
    currency: Currency = Field(description="Валюта платежа")
    description: str = Field(min_length=1, description="Описание платежа")
    payment_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payment_metadata", "metadata"),
        description="Метаданные платежа",
    )
    idempotency_key: str = Field(
        min_length=1, max_length=255, description="Ключ идемпотентности"
    )
    webhook_url: str = Field(min_length=1, max_length=2048, description="URL вебхука")
    status: PaymentStatus = Field(
        default=PaymentStatus.PENDING, description="Начальный статус платежа"
    )


class PaymentCreateDTO(BaseDTO):
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Сумма платежа (больше нуля)",
        examples=[Decimal("150.00")],
    )
    currency: Currency = Field(description="Валюта платежа", examples=[Currency.RUB])
    description: str = Field(
        min_length=1,
        max_length=1000,
        description="Описание назначения платежа",
        examples=["Оплата заказа #12345"],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Пользовательские метаданные в формате JSON",
        examples=[{"order_id": 12345, "customer_id": "cust-99"}],
    )
    webhook_url: str = Field(
        min_length=1,
        max_length=2048,
        description="URL для отправки вебхука с результатом обработки",
        examples=["https://httpbin.org/post"],
    )

    def to_add_dto(self, idempotency_key: str) -> PaymentAddDTO:
        return PaymentAddDTO(
            amount=self.amount,
            currency=self.currency,
            description=self.description,
            payment_metadata=self.metadata,
            idempotency_key=idempotency_key,
            webhook_url=self.webhook_url,
            status=PaymentStatus.PENDING,
        )


class PaymentCreateResponseDTO(BaseDTO):
    payment_id: uuid.UUID = Field(
        validation_alias=AliasChoices("payment_id", "id"),
        description="Идентификатор созданного платежа",
    )
    status: PaymentStatus = Field(description="Статус платежа (pending)")
    created_at: datetime = Field(description="Дата и время создания")


class PaymentResponseDTO(BaseDTO):
    payment_id: uuid.UUID = Field(
        validation_alias=AliasChoices("payment_id", "id"),
        description="Идентификатор платежа",
    )
    amount: Decimal = Field(description="Сумма")
    currency: Currency = Field(description="Валюта")
    description: str = Field(description="Описание")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("payment_metadata", "metadata"),
        description="Метаданные",
    )
    status: PaymentStatus = Field(description="Статус")
    idempotency_key: str = Field(description="Ключ идемпотентности")
    webhook_url: str = Field(description="URL вебхука")
    created_at: datetime = Field(description="Дата создания")
    processed_at: datetime | None = Field(default=None, description="Дата обработки")


class PaymentUpdateDTO(BaseDTO):
    status: PaymentStatus | None = Field(
        default=None, description="Обновленный статус платежа"
    )
    processed_at: datetime | None = Field(
        default=None, description="Дата и время обработки"
    )
