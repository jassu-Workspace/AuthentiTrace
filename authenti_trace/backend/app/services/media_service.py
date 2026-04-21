import os
import uuid
import aiofiles
from fastapi import UploadFile, HTTPException
from app.utils.security import calculate_file_hash
import hashlib

STORAGE_DIR = "./storage" # Ensure directory exists
os.makedirs(STORAGE_DIR, exist_ok=True)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_MIME_TYPES = {
    "image/jpeg", 
    "image/png", 
    "image/webp", 
    "video/mp4", 
    "audio/mpeg"
}

# In a true deployment, import magic to verify the true binary header
# import magic 

async def save_upload_and_hash(file: UploadFile) -> tuple[str, str, str]:
    """Saves the uploaded file to disk and returns (media_id, file_path, file_hash)."""
    
    # 1. MIME Type Verification (Input validation)
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415, 
            detail=f"Unsupported file type: {file.content_type}. Allowed types are: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    media_id = str(uuid.uuid4())
    
    # In production, replace split with strict `python-magic` byte parsing lookup map.
    file_extension = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'bin'
    file_path = os.path.join(STORAGE_DIR, f"{media_id}.{file_extension}")
    
    # Calculate hash incrementally and stream to disk to prevent OOM
    sha256_hash = hashlib.sha256()
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB chunks
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
                
            total_size += len(chunk)
            
            # Streaming validation hook
            if total_size > MAX_FILE_SIZE_BYTES:
                if os.path.exists(file_path):
                    os.remove(file_path)
                raise HTTPException(
                    status_code=413, 
                    detail=f"File content exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES / (1024*1024)} MB."
                )
                
            sha256_hash.update(chunk)
            await out_file.write(chunk)
    
    file_hash = sha256_hash.hexdigest()
    
    return media_id, file_path, file_hash
