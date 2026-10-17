import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from src.config import settings
from src.db.manager import DBManager
from src.utils.enums import Currency, PaymentStatus


@pytest.mark.asyncio
async def test_create_payment_success(client: AsyncClient, db_manager: DBManager):
    idempotency_key = f"key-{uuid.uuid4()}"
    payload = {
        "amount": 250.75,
        "currency": "RUB",
        "description": "Оплата заказа #123",
        "metadata": {"order_id": 123, "user_id": 42},
        "webhook_url": "https://example.com/webhook",
    }

    response = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.idempotency_key: idempotency_key},
    )

    assert response.status_code == 202
    data = response.json()
    assert "payment_id" in data
    assert data["status"] == PaymentStatus.PENDING.value
    assert "created_at" in data

    payment_id = uuid.UUID(data["payment_id"])

    payment_in_db = await db_manager.payments.get_one_or_none(payment_id=payment_id)
    assert payment_in_db is not None
    assert payment_in_db.payment_id == payment_id
    assert payment_in_db.amount == Decimal("250.75")
    assert payment_in_db.currency == Currency.RUB
    assert payment_in_db.idempotency_key == idempotency_key
    assert payment_in_db.payment_metadata == {"order_id": 123, "user_id": 42}

    outbox_events = await db_manager.outbox.get_all()
    matching_events = [
        ev for ev in outbox_events if ev.payload.get("payment_id") == str(payment_id)
    ]
    assert len(matching_events) == 1
    assert matching_events[0].event_type == "PaymentCreated"
    assert matching_events[0].topic == settings.rabbit.queue_name


@pytest.mark.asyncio
async def test_create_payment_unauthorized(client: AsyncClient):
    payload = {
        "amount": 100.00,
        "currency": "RUB",
        "description": "Тест",
        "webhook_url": "https://example.com",
    }

    resp_no_key = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.api_key: ""},
    )
    assert resp_no_key.status_code == 401

    resp_wrong_key = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.api_key: "wrong-invalid-key"},
    )
    assert resp_wrong_key.status_code == 401


@pytest.mark.asyncio
async def test_create_payment_missing_idempotency_key(client: AsyncClient):
    payload = {
        "amount": 100.00,
        "currency": "RUB",
        "description": "Тест",
        "webhook_url": "https://example.com",
    }
    response = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.idempotency_key: ""},
    )
    assert response.status_code == 400
    assert "обязателен" in response.json()["message"]


@pytest.mark.asyncio
async def test_create_payment_idempotency_duplicate(client: AsyncClient):
    idempotency_key = f"key-duplicate-{uuid.uuid4()}"
    payload = {
        "amount": 500.00,
        "currency": "USD",
        "description": "Первая попытка",
        "webhook_url": "https://example.com/webhook",
    }

    resp1 = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.idempotency_key: idempotency_key},
    )
    assert resp1.status_code == 202

    resp2 = await client.post(
        "/api/v1/payments",
        json=payload,
        headers={settings.headers.idempotency_key: idempotency_key},
    )
    assert resp2.status_code == 409
    assert "уже существует" in resp2.json()["message"]


@pytest.mark.asyncio
async def test_create_payment_validation_error(client: AsyncClient):
    idempotency_key = f"key-val-{uuid.uuid4()}"

    resp_bad_amount = await client.post(
        "/api/v1/payments",
        json={
            "amount": -50.0,
            "currency": "RUB",
            "description": "Отрицательная сумма",
            "webhook_url": "https://example.com",
        },
        headers={settings.headers.idempotency_key: idempotency_key},
    )
    assert resp_bad_amount.status_code == 422

    resp_bad_curr = await client.post(
        "/api/v1/payments",
        json={
            "amount": 100.0,
            "currency": "GBP",
            "description": "GBP валюта",
            "webhook_url": "https://example.com",
        },
        headers={settings.headers.idempotency_key: idempotency_key},
    )
    assert resp_bad_curr.status_code == 422


@pytest.mark.asyncio
async def test_get_payment_success(client: AsyncClient, sample_payment):
    response = await client.get(f"/api/v1/payments/{sample_payment.payment_id}/")
    assert response.status_code == 200
    data = response.json()

    assert data["payment_id"] == str(sample_payment.payment_id)
    assert float(data["amount"]) == float(sample_payment.amount)
    assert data["currency"] == sample_payment.currency.value
    assert data["description"] == sample_payment.description
    assert data["status"] == sample_payment.status.value
    assert data["idempotency_key"] == sample_payment.idempotency_key
    assert data["webhook_url"] == sample_payment.webhook_url
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_payment_not_found(client: AsyncClient):
    non_existing_id = uuid.uuid4()
    response = await client.get(f"/api/v1/payments/{non_existing_id}/")
    assert response.status_code == 404
    assert f"Платеж с ID '{non_existing_id}' не найден" in response.json()["message"]


@pytest.mark.asyncio
async def test_get_payment_unauthorized(client: AsyncClient, sample_payment):
    response = await client.get(
        f"/api/v1/payments/{sample_payment.payment_id}/",
        headers={settings.headers.api_key: ""},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_test_endpoint(client: AsyncClient):
    payload = {"test": "data", "status": "ok"}
    response = await client.post("/api/v1/payments/test-webhook/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["received"] == payload
