import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# backend/ directory, independent of the process working directory
BACKEND_DIR = Path(__file__).resolve().parents[2]

SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite+aiosqlite:///{(BACKEND_DIR / 'authentitrace.db').as_posix()}"
)

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session
