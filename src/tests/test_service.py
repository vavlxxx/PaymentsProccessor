import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from src.db.manager import DBManager
from src.schemas.payments import PaymentCreateDTO
from src.services.payments import PaymentsService
from src.utils.enums import Currency, PaymentStatus
from src.utils.exceptions import PaymentAlreadyExistsError, PaymentNotFoundError


@pytest.mark.asyncio
async def test_service_create_payment_and_outbox(db_manager: DBManager):
    """Проверка создания платежа через сервис и формирования outbox события."""
    service = PaymentsService(db_manager)
    idempotency_key = f"key-svc-{uuid.uuid4()}"

    create_dto = PaymentCreateDTO(
        amount=Decimal("350.00"),
        currency=Currency.USD,
        description="Подписка на сервис",
        metadata={"plan": "pro"},
        webhook_url="https://api.example.com/callback",
    )

    result = await service.create_payment(create_dto, idempotency_key=idempotency_key)

    assert result.payment_id is not None
    assert result.status == PaymentStatus.PENDING
    assert result.created_at is not None

    # Проверяем в БД через payment_id
    payment_in_db = await db_manager.payments.get_one(payment_id=result.payment_id)
    assert payment_in_db.payment_id == result.payment_id
    assert payment_in_db.amount == Decimal("350.00")
    assert payment_in_db.currency == Currency.USD

    # Проверяем outbox запись
    outbox_records = await db_manager.outbox.get_all()
    assert len(outbox_records) == 1
    assert outbox_records[0].payload["payment_id"] == str(result.payment_id)


@pytest.mark.asyncio
async def test_service_duplicate_idempotency_key(db_manager: DBManager):
    """Проверка вызова ошибки при повторном использовании ключа идемпотентности."""
    service = PaymentsService(db_manager)
    idempotency_key = f"key-dup-{uuid.uuid4()}"

    create_dto = PaymentCreateDTO(
        amount=Decimal("100.00"),
        currency=Currency.RUB,
        description="Первая оплата",
        webhook_url="https://api.example.com/callback",
    )

    await service.create_payment(create_dto, idempotency_key=idempotency_key)

    with pytest.raises(PaymentAlreadyExistsError):
        await service.create_payment(create_dto, idempotency_key=idempotency_key)


@pytest.mark.asyncio
async def test_service_get_payment(db_manager: DBManager, sample_payment):
    """Проверка получения платежа по payment_id."""
    service = PaymentsService(db_manager)

    result = await service.get_payment(payment_id=sample_payment.payment_id)
    assert result.payment_id == sample_payment.payment_id
    assert result.amount == sample_payment.amount
    assert result.currency == sample_payment.currency

    # Несуществующий ID
    with pytest.raises(PaymentNotFoundError):
        await service.get_payment(payment_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_service_update_payment_status(db_manager: DBManager, sample_payment):
    """Проверка обновления статуса платежа и даты обработки по payment_id."""
    service = PaymentsService(db_manager)
    now = datetime.now(UTC)

    updated = await service.update_payment_status(
        payment_id=sample_payment.payment_id,
        status=PaymentStatus.SUCCEEDED,
        processed_at=now,
    )

    assert updated.payment_id == sample_payment.payment_id
    assert updated.status == PaymentStatus.SUCCEEDED
    assert updated.processed_at is not None

    # Попытка обновления несуществующего платежа
    with pytest.raises(PaymentNotFoundError):
        await service.update_payment_status(
            payment_id=uuid.uuid4(),
            status=PaymentStatus.FAILED,
            processed_at=now,
        )
