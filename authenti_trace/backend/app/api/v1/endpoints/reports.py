from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.database import get_db
from app.models.ledger import VerificationRecord
from app.schemas.verification import ReportResponse
from app.services.ledger_service import prove, review_target

router = APIRouter()


async def _get(db: AsyncSession, ledger_id: str) -> VerificationRecord:
    try:
        record = (await db.execute(select(VerificationRecord).where(VerificationRecord.id == ledger_id))).scalars().first()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    if record is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    return record


# Declared before "/{ledger_id}" so "by-hash" is not read as an id.
@router.get("/by-hash/{file_hash}", response_model=List[ReportResponse], summary="All rows for one file hash")
async def get_reports_by_hash(file_hash: str, db: AsyncSession = Depends(get_db)):
    if len(file_hash) != 64 or any(c not in "0123456789abcdefABCDEF" for c in file_hash):
        raise HTTPException(status_code=422, detail="Expected a 64-character SHA-256 hex string")
    try:
        rows = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.file_hash == file_hash.lower())
            .order_by(VerificationRecord.seq.desc()).limit(20)
        )).scalars().all()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    if not rows:
        raise HTTPException(status_code=404, detail="No record for this file hash")
    return rows


@router.get("/{ledger_id}", response_model=ReportResponse)
async def get_report_by_id(ledger_id: str, db: AsyncSession = Depends(get_db)):
    return await _get(db, ledger_id)


@router.get("/{ledger_id}/proof", summary="Chain proof for one row")
async def get_report_proof(ledger_id: str, db: AsyncSession = Depends(get_db)):
    record = await _get(db, ledger_id)
    try:
        proof = await prove(db, record)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    proof["review_of"] = review_target(record)
    return proof
