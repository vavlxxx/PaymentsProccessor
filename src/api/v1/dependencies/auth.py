from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

from src.api.v1.errors import UnauthorizedHTTPError
from src.config import settings

api_key_header = APIKeyHeader(
    name=settings.headers.api_key,
    auto_error=False,
    description="Статический ключ API для аутентификации запросов",
)


async def verify_api_key(
    api_key: Annotated[str | None, Security(api_key_header)] = None,
) -> str:
    if not api_key or api_key != settings.api.api_key:
        raise UnauthorizedHTTPError(detail="Неверный или отсутствующий API ключ")
    return api_key


ApiKeyDep = Annotated[str, Depends(verify_api_key)]
