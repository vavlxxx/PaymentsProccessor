from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

from src.config import settings


class BaseORM(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=settings.db.naming_convention)
    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """Преобразование модели в словарь."""
        result: dict[str, Any] = {}
        for prop in self.__mapper__.column_attrs:
            result[prop.key] = getattr(self, prop.key)
        return result
