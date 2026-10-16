from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.v1 import router as v1_router
from src.config import settings
from src.db.connection import async_session_maker
from src.db.manager import DBManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    async with DBManager(async_session_maker) as db:
        await db.check()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Асинхронный сервис процессинга платежей",
    description=(
        "Микросервис для асинхронной обработки платежей.\n\n"
        "### Авторизация\n"
        f"Все эндпоинты требуют передачи статического API ключа в заголовке **`{settings.headers.api_key}`**.\n\n"
        "### Идемпотентность\n"
        f"Создание платежа требует передачи обязательного заголовка **`{settings.headers.idempotency_key}`**."
    ),
    version="1.0.0",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": exc.detail,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "message": "Ошибка валидации запроса",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "message": "Ошибка на стороне сервера",
        },
    )


app.include_router(v1_router)
