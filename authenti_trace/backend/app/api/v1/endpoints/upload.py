import logging

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.security import rate_limit_uploads
from app.services.media_service import save_upload_and_hash, remove_file_quietly
from app.services.verification_service import process_verification
from app.schemas.verification import ReportResponse

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/", response_model=ReportResponse, summary="Upload Media and run Verification")
async def upload_and_verify(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _caller: str = Depends(rate_limit_uploads),
):
    # Step 1: Handle strict storage logic and input validation (removes its own partial file on error)
    media_id, file_path, file_hash = await save_upload_and_hash(file)

    try:
        # Step 2: Orchestrate business logic, scoring, and ledger storage
        return await process_verification(db, media_id, file_path, file_hash)
    except HTTPException:
        remove_file_quietly(file_path)
        raise
    except Exception:
        # Do not return exception text to the client; keep details in the server log.
        logger.exception("Verification failed for media %s", media_id)
        remove_file_quietly(file_path)
        raise HTTPException(status_code=500, detail="Verification failed. Please try again.")
