from sqlalchemy import select

from src.models.outbox import OutboxORM
from src.repos.base import BaseRepo
from src.schemas.outbox import OutboxDTO
from src.utils.enums import OutboxStatus


class OutboxRepo(BaseRepo):
    model = OutboxORM
    schema = OutboxDTO

    async def get_pending_and_lock(self, limit: int = 50) -> list[OutboxORM]:
        stmt = (
            select(OutboxORM)
            .where(OutboxORM.status == OutboxStatus.PENDING)
            .order_by(OutboxORM.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
