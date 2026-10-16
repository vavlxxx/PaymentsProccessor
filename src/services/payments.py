import uuid
from typing import cast

from src.schemas.payments import (
    PaymentCreateDTO,
    PaymentCreateResponseDTO,
    PaymentDTO,
    PaymentResponseDTO,
)
from src.services.base import BaseService
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
            await self.db.payments.get_one_or_none(
                idempotency_key=idempotency_key
            )
        )
        if existing:
            raise PaymentAlreadyExistsError(
                f"Платеж с ключом идемпотентности '{idempotency_key}' уже существует"
            )

        add_dto = data.to_add_dto(idempotency_key=idempotency_key)

        try:
            payment = cast(
                PaymentDTO, 
                await self.db.payments.add(add_dto)
            )
            await self.db.commit()
        except ObjectAlreadyExistsError as exc:
            await self.db.rollback()
            raise PaymentAlreadyExistsError(
                f"Платеж с ключом идемпотентности '{idempotency_key}' уже существует"
            ) from exc

        return PaymentCreateResponseDTO(
            payment_id=payment.id,
            status=payment.status,
            created_at=payment.created_at,
        )

    async def get_payment(self, payment_id: uuid.UUID) -> PaymentResponseDTO:
        payment = await self.db.payments.get_one_or_none(id=payment_id)
        if payment is None:
            raise PaymentNotFoundError(f"Платеж с ID '{payment_id}' не найден")

        return PaymentResponseDTO.model_validate(payment)
