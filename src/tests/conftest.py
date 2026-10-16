import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.main import app
from src.api.v1.dependencies.db import get_db
from src.config import settings
from src.db.manager import DBManager
from src.models.base import BaseORM
from src.models.payments import PaymentORM
from src.schemas.payments import PaymentAddDTO
from src.utils.enums import Currency, PaymentStatus


@pytest.fixture
async def async_engine():
    """Create an in-memory SQLite async engine for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(BaseORM.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(BaseORM.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session_factory(async_engine):
    """Create an async sessionmaker bound to the test engine."""
    return async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_manager(session_factory) -> AsyncGenerator[DBManager, None]:
    """Provide a DBManager connected to the in-memory test database."""
    async with DBManager(session_factory) as db:
        yield db


@pytest.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    """Provide an authenticated AsyncClient with in-memory database."""
    async def override_get_db() -> AsyncGenerator[DBManager, None]:
        async with DBManager(session_factory) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    # Use custom lifespan that does not start background relay loop or rabbit connection
    @asynccontextmanager
    async def test_lifespan(_):
        yield

    app.router.lifespan_context = test_lifespan

    transport = ASGITransport(app=app)
    headers = {
        settings.headers.api_key: settings.api.api_key,
        settings.headers.idempotency_key: "default-test-idempotency-key",
    }
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers=headers,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def sample_payment(db_manager: DBManager) -> PaymentORM:
    """Create a sample payment record in the test database."""
    add_dto = PaymentAddDTO(
        payment_id=uuid.uuid4(),
        amount=Decimal("1000.50"),
        currency=Currency.RUB,
        description="Тестовый платеж за услуги",
        payment_metadata={"order_id": 999, "customer": "test-user"},
        idempotency_key=str(uuid.uuid4()),
        webhook_url="https://example.com/webhook",
        status=PaymentStatus.PENDING,
    )
    created = await db_manager.payments.add(add_dto)
    await db_manager.commit()
    payment_orm = await db_manager.payments.get_one(payment_id=created.payment_id)
    return payment_orm
