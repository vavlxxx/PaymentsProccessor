from typing import Any

from faststream.rabbit import RabbitBroker


class RabbitPublisher:
    def __init__(self, broker: RabbitBroker) -> None:
        self.broker = broker

    async def publish(
        self,
        body: dict[str, Any],
        routing_key: str,
        message_id: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        await self.broker.publish(
            message=body,
            queue=routing_key,
            message_id=message_id,
            headers=headers,
            persist=True,
        )
