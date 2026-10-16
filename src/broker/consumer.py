import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from faststream import FastStream
from faststream.middlewares.acknowledgement.config import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitMessage, RabbitQueue

from src.config import settings
from src.db.connection import async_session_maker
from src.db.manager import DBManager
from src.schemas.payments import PaymentDTO
from src.services.payments import PaymentsService
from src.utils.enums import PaymentStatus
from src.utils.exceptions import WebhookDeliveryError

logger = logging.getLogger(__name__)

broker = RabbitBroker(settings.rabbit.url)
app = FastStream(broker)

retry_queue = RabbitQueue(
    name=settings.rabbit.retry_queue_name,
    durable=settings.rabbit.durable,
    arguments={
        "x-message-ttl": settings.rabbit.retry_ttl,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": settings.rabbit.queue_name,
    },
)

payments_queue = RabbitQueue(
    name=settings.rabbit.queue_name,
    durable=settings.rabbit.durable,
    arguments={
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": settings.rabbit.retry_queue_name,
    },
)

dlq_queue = RabbitQueue(
    name=settings.rabbit.dlq_name,
    durable=True,
)


@app.after_startup
async def setup_queues() -> None:
    await broker.declare_queue(retry_queue)
    await broker.declare_queue(payments_queue)
    await broker.declare_queue(dlq_queue)


async def send_to_dlq(message: RabbitMessage, reason: str) -> None:
    headers = dict(message.headers or {})
    headers["x-dlq-reason"] = reason
    await broker.publish(
        message=message.body,
        queue=settings.rabbit.dlq_name,
        headers=headers,
        persist=True,
    )
    await message.ack()


async def send_webhook_with_retries(
    webhook_url: str,
    payload: dict[str, Any],
) -> None:
    max_retries = settings.processing.webhook_max_retries
    backoff = settings.processing.webhook_retry_backoff
    timeout = settings.processing.webhook_timeout

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(webhook_url, json=payload)
                resp.raise_for_status()
                return
        except Exception as exc:
            if attempt < max_retries:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
            else:
                raise WebhookDeliveryError(
                    f"Webhook failed after {max_retries} attempts: {exc}"
                ) from exc


@broker.subscriber(payments_queue, ack_policy=AckPolicy.REJECT_ON_ERROR)
async def process_payment(body: dict[str, Any], message: RabbitMessage) -> None:
    headers = message.headers or {}
    death_header = headers.get("x-death")
    retry_count = 0
    if death_header and isinstance(death_header, list) and len(death_header) > 0:
        retry_count = death_header[0].get("count", 0)

    if retry_count >= settings.rabbit.max_retries:
        await send_to_dlq(
            message, f"Exceeded max retries ({settings.rabbit.max_retries})"
        )
        return

    try:
        payment_id_str = body.get("payment_id")
        if not payment_id_str:
            await send_to_dlq(message, "Missing payment_id")
            return

        payment_id = uuid.UUID(str(payment_id_str))

        async with DBManager(async_session_maker) as db:
            service = PaymentsService(db)
            payment = await db.payments.get_one_or_none(payment_id=payment_id)
            if not payment:
                await send_to_dlq(message, f"Payment {payment_id} not found in DB")
                return

            payment_dto = PaymentDTO.model_validate(payment)
            if payment_dto.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED):
                webhook_payload = {
                    "payment_id": str(payment_dto.payment_id),
                    "status": payment_dto.status.value,
                    "amount": float(payment_dto.amount),
                    "currency": payment_dto.currency.value,
                    "description": payment_dto.description,
                    "metadata": payment_dto.payment_metadata,
                    "created_at": payment_dto.created_at.isoformat(),
                    "processed_at": (
                        payment_dto.processed_at.isoformat()
                        if payment_dto.processed_at
                        else datetime.now(UTC).isoformat()
                    ),
                }
                await send_webhook_with_retries(payment_dto.webhook_url, webhook_payload)
                await message.ack()
                return

            delay = random.uniform(
                settings.processing.min_delay_seconds,
                settings.processing.max_delay_seconds,
            )
            await asyncio.sleep(delay)

            is_success = random.random() < settings.processing.success_rate
            new_status = PaymentStatus.SUCCEEDED if is_success else PaymentStatus.FAILED
            processed_at = datetime.now(UTC)

            await service.update_payment_status(
                payment_id=payment_id,
                status=new_status,
                processed_at=processed_at,
            )

            webhook_payload = {
                "payment_id": str(payment_dto.payment_id),
                "status": new_status.value,
                "amount": float(payment_dto.amount),
                "currency": payment_dto.currency.value,
                "description": payment_dto.description,
                "metadata": payment_dto.payment_metadata,
                "created_at": payment_dto.created_at.isoformat(),
                "processed_at": processed_at.isoformat(),
            }
            await send_webhook_with_retries(payment_dto.webhook_url, webhook_payload)
            await message.ack()

    except WebhookDeliveryError:
        await message.reject(requeue=False)
    except Exception:
        logger.exception("Error processing payment message")
        await message.reject(requeue=False)


async def main() -> None:
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
