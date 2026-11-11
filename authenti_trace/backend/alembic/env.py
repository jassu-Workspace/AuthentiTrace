import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

import app.models.ledger  # noqa: F401  (registers the tables on Base.metadata)
from app.database.database import Base, SQLALCHEMY_DATABASE_URL

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    # Tests and tools may pass a URL through sqlalchemy.url; otherwise use the app's URL.
    url = config.get_main_option("sqlalchemy.url") or SQLALCHEMY_DATABASE_URL
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_async())
