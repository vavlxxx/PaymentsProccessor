import uuid
from datetime import datetime
from typing import cast

from src.config import settings
from src.schemas.outbox import OutboxCreateDTO
from src.schemas.payments import (
    PaymentCreateDTO,
    PaymentCreateResponseDTO,
    PaymentDTO,
    PaymentResponseDTO,
    PaymentUpdateDTO,
)
from src.services.base import BaseService
from src.utils.enums import PaymentStatus
from src.utils.exceptions import (
    ObjectAlreadyExistsError,
    PaymentAlreadyExistsError,
    PaymentNotFoundError,
)


class PaymentsService(BaseService):
    async def create_payment(
        self,
        data: PaymentCreateDTO,
        idempotency_key: str,
    ) -> PaymentCreateResponseDTO:
        existing = cast(
            PaymentDTO | None,
            await self.db.payments.get_one_or_none(idempotency_key=idempotency_key),
        )
        if existing:
            raise PaymentAlreadyExistsError(
                f"Платеж с ключом идемпотентности '{idempotency_key}' уже существует"
            )

        add_dto = data.to_add_dto(idempotency_key=idempotency_key)

        try:
            payment = cast(
                PaymentDTO,
                await self.db.payments.add(add_dto),
            )
        except ObjectAlreadyExistsError as exc:
            await self.db.rollback()
            raise PaymentAlreadyExistsError(
                f"Платеж с ключом идемпотентности '{idempotency_key}' уже существует"
            ) from exc

        outbox_event = OutboxCreateDTO(
            topic=settings.rabbit.queue_name,
            event_type="PaymentCreated",
            payload={
                "payment_id": str(payment.payment_id),
                "amount": float(payment.amount),
                "currency": payment.currency.value,
                "description": payment.description,
                "metadata": payment.payment_metadata,
                "status": payment.status.value,
                "idempotency_key": payment.idempotency_key,
                "webhook_url": payment.webhook_url,
                "created_at": payment.created_at.isoformat(),
            },
        )
        await self.db.outbox.add(outbox_event)
        await self.db.commit()

        return PaymentCreateResponseDTO(
            payment_id=payment.payment_id,
            status=payment.status,
            created_at=payment.created_at,
        )

    async def get_payment(self, payment_id: uuid.UUID) -> PaymentResponseDTO:
        payment = await self.db.payments.get_one_or_none(payment_id=payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Платеж с ID '{payment_id}' не найден")

        return PaymentResponseDTO.model_validate(payment)

    async def update_payment_status(
        self,
        payment_id: uuid.UUID,
        status: PaymentStatus,
        processed_at: datetime,
    ) -> PaymentDTO:
        existing = await self.db.payments.get_one_or_none(payment_id=payment_id)
        if existing is None:
            raise PaymentNotFoundError(f"Платеж с ID '{payment_id}' не найден")

        await self.db.payments.update(
            PaymentUpdateDTO(status=status, processed_at=processed_at),
            payment_id=payment_id,
        )
        await self.db.commit()
        updated = cast(
            PaymentDTO, await self.db.payments.get_one(payment_id=payment_id)
        )
        return updated
