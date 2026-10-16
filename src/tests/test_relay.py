from unittest.mock import AsyncMock

import pytest

from src.broker.relay import run_outbox_relay
from src.db.manager import DBManager
from src.schemas.outbox import OutboxCreateDTO
from src.utils.enums import OutboxStatus


@pytest.mark.asyncio
async def test_outbox_relay_publishes_pending_events(db_manager: DBManager):
    """Тест успешной отправки событий через Outbox Relay."""
    # Создаем 2 события в outbox
    event1 = OutboxCreateDTO(
        topic="payments.new",
        event_type="PaymentCreated",
        payload={"payment_id": "test-1", "amount": 100},
    )
    event2 = OutboxCreateDTO(
        topic="payments.new",
        event_type="PaymentCreated",
        payload={"payment_id": "test-2", "amount": 200},
    )
    await db_manager.outbox.add(event1)
    await db_manager.outbox.add(event2)
    await db_manager.commit()

    mock_publisher = AsyncMock()

    sent = await run_outbox_relay(db_manager, mock_publisher)

    assert sent == 2
    assert mock_publisher.publish.call_count == 2

    # Проверяем, что статус событий изменился на SUCCESS
    all_events = await db_manager.outbox.get_all()
    assert all(e.status == OutboxStatus.SUCCESS for e in all_events)


@pytest.mark.asyncio
async def test_outbox_relay_handles_publisher_error(db_manager: DBManager):
    """Тест обработки ошибки публикации в RabbitMQ и увеличения счетчика ретраев."""
    event = OutboxCreateDTO(
        topic="payments.new",
        event_type="PaymentCreated",
        payload={"payment_id": "test-err", "amount": 50},
    )
    await db_manager.outbox.add(event)
    await db_manager.commit()

    mock_publisher = AsyncMock()
    mock_publisher.publish.side_effect = ConnectionError("RabbitMQ down")

    sent = await run_outbox_relay(db_manager, mock_publisher)

    assert sent == 0
    all_events = await db_manager.outbox.get_all()
    assert len(all_events) == 1
    # retry_count увеличился
    assert all_events[0].retry_count == 1
    assert all_events[0].status == OutboxStatus.PENDING


@pytest.mark.asyncio
async def test_outbox_relay_empty(db_manager: DBManager):
    """Тест работы Relay при пустой таблице outbox."""
    mock_publisher = AsyncMock()
    sent = await run_outbox_relay(db_manager, mock_publisher)
    assert sent == 0
    assert mock_publisher.publish.call_count == 0
