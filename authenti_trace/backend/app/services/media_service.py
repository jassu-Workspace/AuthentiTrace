import hashlib
import logging
import os
import time
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile, HTTPException
from PIL import Image

from app.database.database import BACKEND_DIR

STORAGE_DIR = os.getenv("STORAGE_DIR", str(BACKEND_DIR / "storage"))
os.makedirs(STORAGE_DIR, exist_ok=True)

# Off by default because deleting is irreversible. Set to 30 (or your policy) in production.
MEDIA_RETENTION_DAYS = float(os.getenv("MEDIA_RETENTION_DAYS", "0"))
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Stored extension comes from the declared type, never from the client filename.
# shortcut: the type is client-declared; byte-level sniffing (python-magic) is a later hardening step.
MIME_TO_EXTENSION = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/mpeg": "mp3",
}


MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", str(25_000_000)))  # decompression bombs; analysis needs several float copies of the pixels


def matches_declared_type(content_type: str, head: bytes) -> bool:
    """True when the first bytes look like the declared type. Client headers prove nothing; the bytes do."""
    if content_type == "image/jpeg":
        return head.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if content_type == "video/mp4":
        return head[4:8] == b"ftyp"
    if content_type == "audio/mpeg":
        return head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    return False


def _check_image_size(path: str) -> None:
    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        raise HTTPException(status_code=415, detail="The file could not be read as an image.")
    if width * height > MAX_IMAGE_PIXELS:
        raise HTTPException(status_code=422, detail="The image dimensions are too large.")


async def save_upload_and_hash(file: UploadFile) -> tuple[str, str, str]:
    """Saves the uploaded file to disk and returns (media_id, file_path, file_hash).

    On any failure the partial file is removed before the error propagates.
    """
    extension = MIME_TO_EXTENSION.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed types are: {', '.join(MIME_TO_EXTENSION)}",
        )

    media_id = str(uuid.uuid4())
    file_path = os.path.join(STORAGE_DIR, f"{media_id}.{extension}")

    # Hash incrementally while streaming to disk to avoid loading the file in memory
    sha256_hash = hashlib.sha256()
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB chunks

    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break

                if total_size == 0 and not matches_declared_type(file.content_type or "", chunk[:16]):
                    raise HTTPException(status_code=415, detail="The file content does not match its declared type.")

                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File content exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
                    )

                sha256_hash.update(chunk)
                await out_file.write(chunk)
        if (file.content_type or "").startswith("image/"):
            _check_image_size(file_path)
    except BaseException:
        remove_file_quietly(file_path)
        raise

    return media_id, file_path, sha256_hash.hexdigest()


def remove_file_quietly(path: str) -> None:
    """Delete a stored file; ignore a missing file."""
    Path(path).unlink(missing_ok=True)


def purge_expired_media(retention_days: float = MEDIA_RETENTION_DAYS) -> int:
    """Delete stored files older than the retention period. The ledger keeps the hash and the report.

    shortcut: local disk only. An object-storage adapter (S3) with a lifecycle rule replaces this when needed.
    """
    if retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for entry in os.scandir(STORAGE_DIR):
        if entry.is_file() and entry.stat().st_mtime < cutoff:
            remove_file_quietly(entry.path)
            removed += 1
    if removed:
        logging.getLogger(__name__).info("Purged %s expired media files", removed)
    return removed
