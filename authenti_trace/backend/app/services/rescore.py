"""Re-score stored media under the current pipeline version.

Old rows are never edited. Each re-score appends a new ledger row whose `versions` carries
`rescore_of` (the id of the row it replaces). Media that was purged, or whose bytes no longer match the
recorded hash, is skipped.

Usage (from backend/):  python -m app.services.rescore [--limit N]
"""
import argparse
import asyncio
import glob
import hashlib
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.database import SessionLocal
from app.models.ledger import VerificationRecord
from app.services import media_service
from app.services.ledger_service import REVIEW_CATEGORY, commit_verification
from app.services.verification_service import VERSIONS, analyze_media


def _find_media(media_id: str) -> str | None:
    matches = glob.glob(os.path.join(media_service.STORAGE_DIR, f"{media_id}.*"))
    return matches[0] if matches else None


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def rescore_outdated(db: AsyncSession, limit: int | None = None) -> dict:
    rows = (await db.execute(
        select(
            VerificationRecord.id, VerificationRecord.media_reference_id,
            VerificationRecord.file_hash, VerificationRecord.versions,
        ).where(VerificationRecord.risk_category != REVIEW_CATEGORY).order_by(VerificationRecord.seq)
    )).all()

    up_to_date = {m for _, m, _, v in rows if (v or {}).get("pipeline") == VERSIONS["pipeline"]}
    latest_outdated = {}  # media id -> (row id, file hash) of its newest outdated row
    for row_id, media_id, file_hash, _ in rows:
        if media_id not in up_to_date:
            latest_outdated[media_id] = (row_id, file_hash)

    done = skipped = 0
    for media_id, (row_id, file_hash) in latest_outdated.items():
        if limit is not None and done >= limit:
            break
        path = _find_media(media_id)
        if path is None or await asyncio.to_thread(_sha256, path) != file_hash:
            skipped += 1
            continue
        signals, scoring = await analyze_media(path, file_hash)
        await commit_verification(
            db, media_id, file_hash, scoring.trust_score, scoring.risk_category, scoring.enforcement_action,
            {s.plugin_name: s.model_dump() for s in signals},
            versions={**VERSIONS, "rescore_of": row_id},
        )
        done += 1
    return {"rescored": done, "skipped": skipped}


async def _main(limit: int | None) -> None:
    async with SessionLocal() as db:
        print(await rescore_outdated(db, limit))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int)
    asyncio.run(_main(ap.parse_args().limit))
