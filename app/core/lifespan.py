from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import init_cache
from app.core.clickhouse import close_clickhouse, init_clickhouse
from app.core.config import get_settings
from app.core.database import init_database
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()
    configure_logging(level=settings.log_level, fmt=settings.log_format)

    db = init_database(settings.database_url)
    cache = init_cache(settings.redis_url)
    await db.connect()
    await cache.connect()
    await init_clickhouse()
    try:
        yield
    finally:
        await close_clickhouse()
        await cache.disconnect()
        await db.disconnect()
