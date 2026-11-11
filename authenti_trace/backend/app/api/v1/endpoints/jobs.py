import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.database import get_db
from app.models.ledger import VerificationJob
from app.schemas.verification import JobResponse
from app.services.job_runner import enqueue
from app.services.media_service import remove_file_quietly, save_upload_and_hash
from app.security import rate_limit_uploads
from app.services.object_store import store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=JobResponse, status_code=202, summary="Upload media and start verification")
async def create_job(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_db), _caller: str = Depends(rate_limit_uploads)
):
    """Returns at once with a job id. Poll GET /jobs/{id}; when done it carries the report id."""
    media_id, file_path, file_hash = await save_upload_and_hash(file)
    try:
        key = await asyncio.to_thread(store.put, file_path)  # file_path column holds the storage key
    except Exception:
        logger.exception("Could not store media %s", media_id)
        remove_file_quietly(file_path)
        raise HTTPException(status_code=503, detail="Storage temporarily unavailable")
    if store.remote:
        remove_file_quietly(file_path)  # the worker fetches its own copy

    job_id = str(uuid.uuid4())  # keep a local copy: the ORM object expires after commit
    job = VerificationJob(
        id=job_id, status="queued", media_id=media_id, file_path=key, file_hash=file_hash, attempts=0
    )
    try:
        db.add(job)
        await db.commit()
    except SQLAlchemyError:
        logger.exception("Could not create job for media %s", media_id)
        await db.rollback()
        await asyncio.to_thread(store.delete, key)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    enqueue(job_id)
    return JobResponse(job_id=job_id, status="queued", attempts=0)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job = (await db.execute(select(VerificationJob).where(VerificationJob.id == job_id))).scalars().first()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
