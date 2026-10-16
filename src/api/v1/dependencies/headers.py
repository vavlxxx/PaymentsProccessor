from typing import Annotated

from fastapi import Depends, Header

from src.api.v1.errors import BadRequestHTTPError
from src.config import settings


async def get_idempotency_key(
    idempotency_key: Annotated[
        str | None,
        Header(
            alias=settings.headers.idempotency_key,
            description="Уникальный ключ идемпотентности для защиты от повторных платежей",
        ),
    ] = None,
) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise BadRequestHTTPError(
            detail=f"Заголовок '{settings.headers.idempotency_key}' обязателен"
        )
    return idempotency_key.strip()


IdempotencyKeyDep = Annotated[str, Depends(get_idempotency_key)]
