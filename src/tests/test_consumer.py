import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.broker.consumer import (
    process_payment,
    send_webhook_with_retries,
)
from src.db.manager import DBManager
from src.schemas.payments import PaymentAddDTO
from src.utils.enums import Currency, PaymentStatus
from src.utils.exceptions import WebhookDeliveryError


async def test_send_webhook_success():
    req = httpx.Request("POST", "https://example.com/webhook")
    mock_resp = httpx.Response(status_code=200, request=req)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        await send_webhook_with_retries(
            "https://example.com/webhook",
            {"payment_id": "test-id", "status": "succeeded"},
        )
        assert mock_post.call_count == 1


async def test_send_webhook_retry_then_success():
    req = httpx.Request("POST", "https://example.com/webhook")
    mock_error_resp = httpx.Response(status_code=500, request=req)
    mock_ok_resp = httpx.Response(status_code=200, request=req)

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_post.side_effect = [
            httpx.HTTPStatusError(
                "Server error", request=req, response=mock_error_resp
            ),
            mock_ok_resp,
        ]
        await send_webhook_with_retries(
            "https://example.com/webhook",
            {"payment_id": "test-id", "status": "succeeded"},
        )
        assert mock_post.call_count == 2
        assert mock_sleep.call_count == 1


async def test_send_webhook_exhausts_retries():
    req = httpx.Request("POST", "https://example.com/webhook")
    mock_error_resp = httpx.Response(status_code=502, request=req)

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_post.side_effect = httpx.HTTPStatusError(
            "Bad Gateway", request=req, response=mock_error_resp
        )
        with pytest.raises(WebhookDeliveryError):
            await send_webhook_with_retries(
                "https://example.com/webhook",
                {"payment_id": "test-id", "status": "failed"},
            )
        assert mock_post.call_count == 3


async def test_process_payment_missing_id():
    mock_message = AsyncMock()
    mock_message.headers = {}
    mock_message.body = {}

    with patch("src.broker.consumer.send_to_dlq", new_callable=AsyncMock) as mock_dlq:
        await process_payment({}, mock_message)
        mock_dlq.assert_called_once()
        assert "Missing payment_id" in mock_dlq.call_args[0][1]


async def test_process_payment_not_found(session_factory):
    non_existing_id = str(uuid.uuid4())
    mock_message = AsyncMock()
    mock_message.headers = {}
    mock_message.body = {"payment_id": non_existing_id}

    with (
        patch("src.broker.consumer.send_to_dlq", new_callable=AsyncMock) as mock_dlq,
        patch("src.broker.consumer.async_session_maker", session_factory),
    ):
        await process_payment({"payment_id": non_existing_id}, mock_message)
        mock_dlq.assert_called_once()
        assert "not found in DB" in mock_dlq.call_args[0][1]


async def test_process_payment_exceeded_retries():
    mock_message = AsyncMock()
    mock_message.headers = {"x-death": [{"count": 3, "queue": "payments.new"}]}
    mock_message.body = {"payment_id": str(uuid.uuid4())}

    with patch("src.broker.consumer.send_to_dlq", new_callable=AsyncMock) as mock_dlq:
        await process_payment({"payment_id": str(uuid.uuid4())}, mock_message)
        mock_dlq.assert_called_once()
        assert "Exceeded max retries" in mock_dlq.call_args[0][1]


async def test_process_payment_success_flow(session_factory, db_manager: DBManager):
    payment_id = uuid.uuid4()
    add_dto = PaymentAddDTO(
        payment_id=payment_id,
        amount=Decimal("500.00"),
        currency=Currency.RUB,
        description="Тестовый заказ",
        payment_metadata={},
        idempotency_key=str(uuid.uuid4()),
        webhook_url="https://example.com/webhook",
        status=PaymentStatus.PENDING,
    )
    await db_manager.payments.add(add_dto)
    await db_manager.commit()

    mock_message = AsyncMock()
    mock_message.headers = {}
    mock_message.body = {"payment_id": str(payment_id)}

    with (
        patch("src.broker.consumer.async_session_maker", session_factory),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "src.broker.consumer.send_webhook_with_retries", new_callable=AsyncMock
        ) as mock_webhook,
    ):
        await process_payment({"payment_id": str(payment_id)}, mock_message)

        mock_message.ack.assert_called_once()
        mock_webhook.assert_called_once()

        updated_payment = await db_manager.payments.get_one(payment_id=payment_id)
        assert updated_payment.status in (PaymentStatus.SUCCEEDED, PaymentStatus.FAILED)
        assert updated_payment.processed_at is not None
