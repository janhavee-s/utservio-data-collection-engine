import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database.connection import Base

TEST_DATABASE_URL = os.environ.get(
    "CI_TEST_DATABASE_URL",
    "postgresql+asyncpg://utservio_test:test_password@localhost:5433/utservio_ci_test",
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)

    yield session

    await transaction.rollback()
    await connection.close()
