from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List
from app.database.database import get_db
from app.models.ledger import VerificationRecord
from app.utils.security import calculate_ledger_hash
from app.services.ledger_service import GENESIS_HASH

router = APIRouter()

@router.get("/metrics", summary="Get dashboard metrics")
async def get_dashboard_metrics(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(VerificationRecord))
        records = result.scalars().all()

        risk_distribution = {"LOW_RISK": 0, "MEDIUM_RISK": 0, "HIGH_RISK": 0}
        for r in records:
            if r.risk_category in risk_distribution:
                risk_distribution[r.risk_category] += 1

        return {
            "total_verifications": len(records),
            "risk_distribution": risk_distribution
        }
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")

@router.get("/audit", summary="Audit Tamper-Evident Ledger Integrity")
async def audit_ledger(db: AsyncSession = Depends(get_db)):
    """Walks the tree to ensure no database rows were tampered with externally."""
    try:
        result = await db.execute(select(VerificationRecord).order_by(VerificationRecord.created_at.asc()))
        records = result.scalars().all()

        is_valid = True
        previous_hash = GENESIS_HASH
        errors = []

        for r in records:
            payload = {
                "media_id": str(r.media_reference_id),
                "file_hash": str(r.file_hash),
                "score": f"{r.composite_score:.2f}",
                "risk": str(r.risk_category),
                "action": str(r.enforcement_action),
                "telemetry": r.signal_telemetry
            }

            expected_hash = calculate_ledger_hash(previous_hash, payload)
            if expected_hash != r.current_hash:
                is_valid = False
                errors.append(f"Row {r.id} tampered! Expected hash {expected_hash}, got {r.current_hash}")

            previous_hash = r.current_hash

        return {"ledger_intact": is_valid, "chain_length": len(records), "errors": errors}
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
