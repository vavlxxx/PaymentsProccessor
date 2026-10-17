import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Path, status

from src.api.v1.dependencies import ApiKeyDep, DatabaseDep, IdempotencyKeyDep
from src.api.v1.errors import (
    DBQueryHTTPError,
    PaymentAlreadyExistsHTTPError,
    PaymentNotFoundHTTPError,
)
from src.api.v1.examples import (
    CREATE_PAYMENT_EXAMPLES,
    CREATE_PAYMENT_RESPONSES,
    GET_PAYMENT_RESPONSES,
    PAYMENT_ID_EXAMPLE,
)
from src.schemas.payments import (
    PaymentCreateDTO,
    PaymentCreateResponseDTO,
    PaymentResponseDTO,
)
from src.services.payments import PaymentsService
from src.utils.exceptions import (
    DBQueryError,
    PaymentAlreadyExistsError,
    PaymentNotFoundError,
)

router = APIRouter(prefix="/payments", tags=["Платежи"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Создание платежа",
    responses=CREATE_PAYMENT_RESPONSES,
)
async def create_payment(
    data: Annotated[
        PaymentCreateDTO,
        Body(openapi_examples=CREATE_PAYMENT_EXAMPLES),
    ],
    idempotency_key: IdempotencyKeyDep,
    _auth: ApiKeyDep,
    db: DatabaseDep,
) -> PaymentCreateResponseDTO:
    try:
        return await PaymentsService(db).create_payment(
            data=data,
            idempotency_key=idempotency_key,
        )
    except PaymentAlreadyExistsError as exc:
        raise PaymentAlreadyExistsHTTPError(str(exc)) from exc
    except DBQueryError as exc:
        raise DBQueryHTTPError from exc


@router.get(
    "/{payment_id}/",
    status_code=status.HTTP_200_OK,
    summary="Получение информации о платеже",
    responses=GET_PAYMENT_RESPONSES,
)
async def get_payment(
    payment_id: Annotated[
        uuid.UUID,
        Path(
            description="Уникальный идентификатор платежа (UUID)",
            examples=[PAYMENT_ID_EXAMPLE],
        ),
    ],
    _auth: ApiKeyDep,
    db: DatabaseDep,
) -> PaymentResponseDTO:
    try:
        return await PaymentsService(db).get_payment(payment_id=payment_id)
    except PaymentNotFoundError as exc:
        raise PaymentNotFoundHTTPError(str(exc)) from exc
    except DBQueryError as exc:
        raise DBQueryHTTPError from exc


@router.webhooks.post(
    "/test-webhook/",
    status_code=status.HTTP_200_OK,
    summary="Тестовый эндпоинт для приема вебхуков",
)
async def test_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok", "received": payload}
