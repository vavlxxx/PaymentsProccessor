import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class PaymentEventPayload(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    idempotency_key: str
    webhook_url: str
    created_at: str


class WebhookNotificationPayload(BaseModel):
    payment_id: uuid.UUID
    status: str
    amount: Decimal
    currency: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    processed_at: str
