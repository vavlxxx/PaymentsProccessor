"""Базовые хелперы и стандартные ответы ошибок для OpenAPI документации."""

from typing import Any

from src.config import settings
from src.schemas.errors import ErrorResponseDTO


def error_response(
    description: str,
    error: str,
    message: str,
) -> dict[str, Any]:
    """Генерация документации ошибок для Swagger/OpenAPI."""
    return {
        "model": ErrorResponseDTO,
        "description": description,
        "content": {
            "application/json": {
                "example": {
                    "error": error,
                    "message": message,
                }
            }
        },
    }


BAD_REQUEST_RESPONSE = error_response(
    f"Некорректный запрос или отсутствует заголовок {settings.headers.idempotency_key}",
    "BAD_REQUEST",
    f"Заголовок '{settings.headers.idempotency_key}' обязателен",
)

UNAUTHORIZED_RESPONSE = error_response(
    f"Неверный или отсутствующий API ключ в заголовке {settings.headers.api_key}",
    "UNAUTHORIZED",
    "Неверный или отсутствующий API ключ",
)

NOT_FOUND_RESPONSE = error_response(
    "Платеж не найден",
    "PAYMENT_NOT_FOUND",
    "Платеж не найден",
)

CONFLICT_RESPONSE = error_response(
    "Конфликт ключа идемпотентности",
    "PAYMENT_ALREADY_EXISTS",
    "Платеж с таким ключом идемпотентности уже существует",
)

VALIDATION_RESPONSE = error_response(
    "Ошибка валидации данных запроса",
    "VALIDATION_ERROR",
    "Некорректные параметры платежа",
)
