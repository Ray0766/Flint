"""Alembic 迁移入口（异步 asyncpg 引擎，E11：单线头 + 每迁移可 downgrade）。"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DEFAULT_URL = "postgresql+asyncpg://flint:flint@localhost:55432/flint"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
