from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.repos.outbox import OutboxRepo
from src.repos.payments import PaymentsRepo
from src.utils.exceptions import DBConnectionError


class DBManager:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def __aenter__(self) -> Self:
        self.session: AsyncSession = self.session_factory()
        self.payments = PaymentsRepo(self.session)
        self.outbox = OutboxRepo(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def check(self) -> None:
        try:
            await self.session.execute(text("SELECT 1"))
        except Exception as exc:
            raise DBConnectionError("Ошибка соединения с базой данных") from exc
