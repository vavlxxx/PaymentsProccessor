"""Примеры запросов и ответов эндпоинтов платежей для OpenAPI документации."""

from typing import Any

from src.api.v1.examples.common import (
    BAD_REQUEST_RESPONSE,
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.schemas.payments import (
    PaymentCreateResponseDTO,
    PaymentResponseDTO,
)

PAYMENT_ID_EXAMPLE = "123e4567-e89b-12d3-a456-426614174000"

CREATE_PAYMENT_EXAMPLES: dict[str, Any] = {
    "rub_payment": {
        "summary": "Платеж в рублях",
        "value": {
            "amount": 1500.00,
            "currency": "RUB",
            "description": "Оплата заказа #1024 в интернет-магазине",
            "metadata": {"order_id": 1024, "customer_id": "cust-887"},
            "webhook_url": "https://merchant.example.com/api/v1/webhook",
        },
    },
    "usd_payment": {
        "summary": "Платеж в долларах",
        "value": {
            "amount": 49.99,
            "currency": "USD",
            "description": "Подписка на сервис Pro Plan (1 месяц)",
            "metadata": {"plan": "pro_monthly"},
            "webhook_url": "https://merchant.example.com/api/v1/webhook",
        },
    },
}

CREATE_PAYMENT_RESPONSES: dict[int | str, dict[str, Any]] = {
    202: {
        "description": "Платеж успешно принят в обработку",
        "model": PaymentCreateResponseDTO,
    },
    400: BAD_REQUEST_RESPONSE,
    401: UNAUTHORIZED_RESPONSE,
    409: CONFLICT_RESPONSE,
    422: VALIDATION_RESPONSE,
}

GET_PAYMENT_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Детальная информация о платеже",
        "model": PaymentResponseDTO,
    },
    400: BAD_REQUEST_RESPONSE,
    401: UNAUTHORIZED_RESPONSE,
    404: NOT_FOUND_RESPONSE,
}
