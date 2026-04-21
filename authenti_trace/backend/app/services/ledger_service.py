import json
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.models.ledger import VerificationRecord
from app.utils.security import calculate_ledger_hash
from typing import Optional

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

async def get_latest_hash(db: AsyncSession) -> str:
    """Fetch the current highest record in the hash chain."""
    result = await db.execute(
        select(VerificationRecord)
        .order_by(VerificationRecord.created_at.desc())
        .limit(1)
        # .with_for_update() # Note: In Production PostgreSQL, explicitly lock this row to prevent race conditions natively.
    )
    latest_record = result.scalars().first()
    if latest_record:
        return latest_record.current_hash
    return GENESIS_HASH

async def commit_verification(
    db: AsyncSession, 
    media_id: str, 
    file_hash: str, 
    score: float, 
    risk: str, 
    action: str, 
    telemetry: dict
) -> VerificationRecord:
    """Commits a tamper-evident record to the database ledger using sequential hashing."""
    
    previous_hash = await get_latest_hash(db)
    
    # Establish canonical data structure for strict hashing regardless of OS/Python version.
    # We serialize floats to strings truncating imprecision to prevent hash collisions.
    payload_for_hash = {
        "media_id": str(media_id),
        "file_hash": str(file_hash),
        "score": f"{score:.2f}",
        "risk": str(risk),
        "action": str(action),
        "telemetry": telemetry # nested dicts sort_keys securely applied in security.py
    }
    
    current_hash = calculate_ledger_hash(previous_hash, payload_for_hash)
    
    new_record = VerificationRecord(
        media_reference_id=media_id,
        file_hash=file_hash,
        composite_score=score,
        risk_category=risk,
        enforcement_action=action,
        signal_telemetry=telemetry,
        previous_hash=previous_hash,
        current_hash=current_hash
    )
    
    try:
        db.add(new_record)
        await db.commit()
        await db.refresh(new_record)
    except SQLAlchemyError:
        await db.rollback()
        raise
    
    return new_record
