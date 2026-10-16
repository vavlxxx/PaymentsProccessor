from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends

from src.db.connection import async_session_maker
from src.db.manager import DBManager


async def get_db() -> AsyncGenerator[DBManager, None]:
    async with DBManager(async_session_maker) as db:
        yield db


DatabaseDep = Annotated[DBManager, Depends(get_db)]
