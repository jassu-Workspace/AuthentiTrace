import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.database.database import BACKEND_DIR


def make_config(url: str | None = None) -> Config:
    cfg = Config(str(Path(BACKEND_DIR) / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(BACKEND_DIR) / "alembic"))
    if url:
        cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


async def upgrade_to_head(url: str | None = None) -> None:
    """Run migrations in a worker thread (alembic's env.py starts its own event loop)."""
    await asyncio.to_thread(command.upgrade, make_config(url), "head")
