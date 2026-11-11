"""Celery entry point. Used only when CELERY_BROKER_URL is set (for example redis://localhost:6379/0).

Run a worker:  celery -A app.celery_app worker -l info          (Linux, macOS)
               celery -A app.celery_app worker -l info -P solo  (Windows)
Several workers and the API can run at once: the ledger's unique seq/previous_hash columns keep the chain
linear, and acks_late means a job whose worker died is delivered again.
"""
import asyncio
import os

from celery import Celery
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import database

BROKER_URL = os.getenv("CELERY_BROKER_URL", "")

celery_app = Celery("authentitrace", broker=BROKER_URL or "memory://")
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # long CPU jobs: take one at a time
    task_time_limit=int(os.getenv("JOB_HARD_TIME_LIMIT_SECONDS", "600")),
    broker_connection_retry_on_startup=True,
)


async def _run(job_id: str) -> None:
    from app.services.job_runner import run_job  # imported late: job_runner imports this module

    # A fresh engine per task: each task runs in its own event loop, and pooled connections cannot cross loops.
    engine = create_async_engine(database.SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
    try:
        await run_job(job_id, async_sessionmaker(bind=engine, expire_on_commit=False))
    finally:
        await engine.dispose()


@celery_app.task(name="authentitrace.verify_job")
def verify_job(job_id: str) -> None:
    asyncio.run(_run(job_id))
