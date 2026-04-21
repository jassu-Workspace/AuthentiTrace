from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.services.media_service import save_upload_and_hash
from app.services.verification_service import process_verification
from app.schemas.verification import ReportResponse

router = APIRouter()

@router.post("/", response_model=ReportResponse, summary="Upload Media and run Verification")
async def upload_and_verify(
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    try:
        # Step 1: Handle strict storage logic and input validation
        media_id, file_path, file_hash = await save_upload_and_hash(file)
        
        # Step 2: Orchestrate Business logic, scoring, and ledger storage
        report = await process_verification(db, media_id, file_path, file_hash)
        
        return report
    except HTTPException as e:
        # Re-raise known HTTP exceptions (like File Size Limit or MIME mismatch) cleanly
        raise e
    except Exception as e:
        # Generic fallback for internal crashes
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
