from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from app.database.database import get_db
from app.models.ledger import VerificationRecord
from app.schemas.verification import ReportResponse

router = APIRouter()

@router.get("/{ledger_id}", response_model=ReportResponse)
async def get_report_by_id(ledger_id: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(VerificationRecord).where(VerificationRecord.id == ledger_id))
        record = result.scalars().first()
        if not record:
            raise HTTPException(status_code=404, detail="Log entry not found")
        return record
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
