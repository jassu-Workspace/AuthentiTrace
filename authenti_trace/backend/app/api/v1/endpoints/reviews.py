from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.database import get_db
from app.models.ledger import VerificationRecord
from app.schemas.verification import PendingReview, ReportResponse, ReviewRequest
from app.security import ANONYMOUS, require_api_key
from app.services.ledger_service import REVIEWABLE_ACTIONS, commit_review, reviewed_ids

router = APIRouter()


@router.get("/pending", response_model=List[PendingReview], summary="Verdicts waiting for a human decision")
async def list_pending(limit: int = 100, db: AsyncSession = Depends(get_db)):
    limit = max(1, min(limit, 500))
    try:
        done = await reviewed_ids(db)
        rows = (await db.execute(
            select(VerificationRecord)
            .where(VerificationRecord.enforcement_action.in_(REVIEWABLE_ACTIONS))
            .order_by(VerificationRecord.seq.desc())
            .limit(limit + len(done))
        )).scalars().all()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

    pending = [r for r in rows if r.id not in done][:limit]
    return [
        PendingReview(
            id=r.id, seq=r.seq, media_reference_id=r.media_reference_id, composite_score=r.composite_score,
            risk_category=r.risk_category, enforcement_action=r.enforcement_action,
            reason=((r.signal_telemetry or {}).get("_decision") or {}).get("reason", ""),
            created_at=r.created_at,
        )
        for r in pending
    ]


@router.post("/{ledger_id}", response_model=ReportResponse, status_code=201, summary="Record a human decision")
async def decide(
    ledger_id: str, body: ReviewRequest, db: AsyncSession = Depends(get_db), identity: str = Depends(require_api_key)
):
    """Appends a new ledger row that points at the reviewed row. The original row is never changed."""
    try:
        original = (await db.execute(select(VerificationRecord).where(VerificationRecord.id == ledger_id))).scalars().first()
        if original is None:
            raise HTTPException(status_code=404, detail="Log entry not found")
        if original.enforcement_action not in REVIEWABLE_ACTIONS:
            raise HTTPException(status_code=422, detail="This verdict does not need a review")
        if ledger_id in await reviewed_ids(db):
            raise HTTPException(status_code=409, detail="This verdict was already reviewed")
        # With auth on, the reviewer is who the API key says, never what the request claims.
        reviewer = identity if identity != ANONYMOUS else (body.reviewer.strip() or "anonymous")
        return await commit_review(db, original, body.decision, body.note.strip(), reviewer)
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
