import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import BACKEND_DIR, get_db
from app.security import rate_limit_heavy
from app.models.ledger import VerificationRecord
from app.services.drift import drift_status, histogram, psi, score_windows
from app.services.ledger_service import REVIEW_CATEGORY, REVIEWABLE_ACTIONS, audit_chain, reviewed_ids

router = APIRouter()

EVAL_RESULTS_PATH = Path(os.getenv("EVAL_RESULTS_PATH", str(BACKEND_DIR / "eval" / "results" / "latest.json")))
DRIFT_WINDOW_DAYS = 7


@router.get("/metrics", summary="Get dashboard metrics")
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            select(VerificationRecord.risk_category, func.count())
            .where(VerificationRecord.risk_category != REVIEW_CATEGORY)  # human decisions are not verifications
            .group_by(VerificationRecord.risk_category)
        )
        counts = {category: count for category, count in result.all()}

        risk_distribution = {k: counts.get(k, 0) for k in ("LOW_RISK", "MEDIUM_RISK", "HIGH_RISK", "UNKNOWN")}
        return {
            "total_verifications": sum(counts.values()),
            "risk_distribution": risk_distribution,
        }
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")


@router.get("/audit", summary="Audit Tamper-Evident Ledger Integrity")
async def audit_ledger(db: AsyncSession = Depends(get_db), _caller: str = Depends(rate_limit_heavy)):
    """Walks the chain to ensure no database rows were changed, removed or reordered."""
    try:
        return await audit_chain(db)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")


@router.get("/quality", summary="Review backlog, score distribution, drift and the latest labeled accuracy")
async def get_quality(db: AsyncSession = Depends(get_db)):
    try:
        baseline, recent = await score_windows(db, DRIFT_WINDOW_DAYS)
        done = await reviewed_ids(db)
        waiting = (await db.execute(
            select(VerificationRecord.id).where(VerificationRecord.enforcement_action.in_(REVIEWABLE_ACTIONS))
        )).scalars().all()
        backlog = len([i for i in waiting if i not in done])
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    drift = psi(baseline, recent)

    latest_eval = None
    if EVAL_RESULTS_PATH.exists():
        try:
            report = json.loads(EVAL_RESULTS_PATH.read_text(encoding="utf-8"))
            latest_eval = {**report["summary"], "split": report.get("split"),
                           "evaluated_at": EVAL_RESULTS_PATH.stat().st_mtime}
            latest_eval.pop("calibration", None)
        except (OSError, ValueError, KeyError):
            latest_eval = None

    return {
        "review_backlog": backlog,
        "score_distribution": histogram(recent),
        "recent_count": len(recent),
        "drift": {"psi": drift, "status": drift_status(drift), "window_days": DRIFT_WINDOW_DAYS},
        "latest_eval": latest_eval,
    }
