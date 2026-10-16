import asyncio
import logging
import sys
from pathlib import Path

from faststream.rabbit import RabbitBroker

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.broker.publisher import RabbitPublisher
from src.config import settings
from src.db.connection import async_session_maker
from src.db.manager import DBManager
from src.utils.enums import OutboxStatus

logger = logging.getLogger(__name__)


async def run_outbox_relay(
    db: DBManager,
    publisher: RabbitPublisher,
) -> int:
    try:
        outboxes = await db.outbox.get_pending_and_lock(
            limit=settings.outbox.batch_size
        )
        if not outboxes:
            await db.rollback()
            return 0

        sent_count = 0
        for outbox in outboxes:
            try:
                await publisher.publish(
                    body=outbox.payload,
                    routing_key=outbox.topic,
                    message_id=str(outbox.event_id),
                )
                outbox.status = OutboxStatus.SUCCESS
                sent_count += 1
            except Exception:  # noqa: BLE001
                outbox.retry_count += 1
                if outbox.retry_count >= settings.rabbit.max_retries:
                    outbox.status = OutboxStatus.FAILED

        await db.commit()
        return sent_count
    except Exception:  # noqa: BLE001
        await db.rollback()
        return 0


async def run_relay_loop() -> None:
    broker = RabbitBroker(settings.rabbit.url)
    publisher = RabbitPublisher(broker=broker)

    while True:
        try:
            await broker.connect()
            try:
                while True:
                    async with DBManager(async_session_maker) as db:
                        await run_outbox_relay(db, publisher)
                    await asyncio.sleep(settings.outbox.poll_interval)
            finally:
                await broker.close()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            await asyncio.sleep(3)


async def main() -> None:
    await run_relay_loop()


if __name__ == "__main__":
    asyncio.run(main())
