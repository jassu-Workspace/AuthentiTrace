import os
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.database.database import get_db
from app.models.ledger import VerificationJob, VerificationRecord, utcnow
from app.services import ledger_service

router = APIRouter()
public_router = APIRouter()  # no authentication: load balancers and orchestrators call it


@public_router.get("/health", summary="Liveness and database check")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok"}


@router.get("/metrics", response_class=PlainTextResponse, summary="Prometheus metrics")
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    try:
        by_status = dict((await db.execute(
            select(VerificationJob.status, func.count()).group_by(VerificationJob.status))).all())
        oldest_queued = (await db.execute(
            select(func.min(VerificationJob.created_at)).where(VerificationJob.status == "queued"))).scalar()
        head_seq = (await db.execute(select(func.max(VerificationRecord.seq)))).scalar() or 0
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    anchor_age = -1.0  # -1 means there is no anchor file
    if ledger_service.ANCHOR_PATH and os.path.exists(ledger_service.ANCHOR_PATH):
        anchor_age = time.time() - os.path.getmtime(ledger_service.ANCHOR_PATH)

    gauges = {
        "authentitrace_ledger_head_seq": float(head_seq),
        "authentitrace_anchor_age_seconds": anchor_age,
        "authentitrace_queue_oldest_age_seconds": (utcnow() - oldest_queued).total_seconds() if oldest_queued else 0.0,
    }
    for status in ("queued", "running", "done", "failed"):
        gauges[f'authentitrace_jobs{{status="{status}"}}'] = float(by_status.get(status, 0))
    return metrics.render(gauges)
