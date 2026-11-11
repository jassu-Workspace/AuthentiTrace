"""Background verification jobs.

Two ways to run a job, chosen by enqueue():
- CELERY_BROKER_URL set: a Celery task (any number of worker processes, survives API restarts).
- not set: an asyncio task inside the API process (zero setup, for development and small installs).
The job row is claimed atomically (queued -> running), so a job never runs twice at once.
"""
import asyncio
import logging
import os
from datetime import timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.celery_app import BROKER_URL, verify_job
from app.database.database import SessionLocal
from app.models.ledger import VerificationJob, utcnow
from app.services.media_service import remove_file_quietly
from app.services.object_store import store
from app.services.verification_service import process_verification

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "2"))
# With a broker, a job left "running" this long is treated as lost (its worker died) and queued again.
STALE_RUNNING_SECONDS = int(os.getenv("JOB_STALE_SECONDS", "900"))
_running: set[asyncio.Task] = set()  # strong references so tasks are not garbage collected


async def _set(db: AsyncSession, job_id: str, **values) -> None:
    await db.execute(update(VerificationJob).where(VerificationJob.id == job_id).values(updated_at=utcnow(), **values))
    await db.commit()


async def _claim(db: AsyncSession, job_id: str) -> bool:
    """Atomically move queued -> running. False means another runner already took the job."""
    result = await db.execute(
        update(VerificationJob)
        .where(VerificationJob.id == job_id, VerificationJob.status == "queued")
        .values(status="running", updated_at=utcnow())
    )
    await db.commit()
    return result.rowcount == 1


async def run_job(job_id: str, session_factory: Callable[[], AsyncSession] = SessionLocal) -> None:
    """Run one job to done or failed. A failed job writes no ledger row."""
    async with session_factory() as db:
        job = (await db.execute(select(VerificationJob).where(VerificationJob.id == job_id))).scalars().first()
        if job is None or job.status != "queued":
            return
        media_id, key, file_hash, attempts = job.media_id, job.file_path, job.file_hash, job.attempts

        if not await asyncio.to_thread(store.exists, key):
            # Purged or lost media must not produce a verdict (and a ledger row) about nothing.
            await _set(db, job_id, status="failed", error="MEDIA_MISSING")
            return
        if not await _claim(db, job_id):
            return

        local_path = None
        try:
            while attempts < MAX_ATTEMPTS:
                attempts += 1
                await _set(db, job_id, status="running", attempts=attempts)
                try:
                    local_path = await asyncio.to_thread(store.fetch, key)
                    report = await process_verification(db, media_id, local_path, file_hash)
                except Exception:
                    logger.exception("Job %s attempt %s failed", job_id, attempts)
                    await db.rollback()
                    continue
                await _set(db, job_id, status="done", report_id=report.id)
                metrics.inc("authentitrace_jobs_finished_total", status="done")
                return

            await _set(db, job_id, status="failed", error="VERIFICATION_FAILED")
            metrics.inc("authentitrace_jobs_finished_total", status="failed")
            await asyncio.to_thread(store.delete, key)
        finally:
            if store.remote and local_path:
                remove_file_quietly(local_path)  # the S3 object stays; only the local cache copy goes


def enqueue(job_id: str) -> None:
    if BROKER_URL:
        verify_job.delay(job_id)
        return
    task = asyncio.get_running_loop().create_task(run_job(job_id))
    _running.add(task)
    task.add_done_callback(_running.discard)


async def recover_jobs() -> int:
    """After a restart, queue again every job that was queued, or running and abandoned."""
    stale_after = timedelta(seconds=STALE_RUNNING_SECONDS if BROKER_URL else 0)
    async with SessionLocal() as db:
        await db.execute(
            update(VerificationJob)
            .where(VerificationJob.status == "running", VerificationJob.updated_at <= utcnow() - stale_after)
            .values(status="queued", updated_at=utcnow())
        )
        await db.commit()
        ids = (await db.execute(select(VerificationJob.id).where(VerificationJob.status == "queued"))).scalars().all()
    for job_id in ids:
        enqueue(job_id)
    return len(ids)
