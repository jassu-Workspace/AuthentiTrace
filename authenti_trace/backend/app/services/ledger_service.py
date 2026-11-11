import asyncio
import json
import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database.database import BACKEND_DIR
from app.models.ledger import VerificationRecord, utcnow
from app.utils.security import calculate_ledger_hash

logger = logging.getLogger(__name__)

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# hash_version 1: media, file hash, score, risk, action, telemetry (old rows).
# hash_version 2: version 1 plus seq, created_at and versions.
CURRENT_HASH_VERSION = 2

# Serializes writers inside one process. Across processes the unique seq and
# previous_hash columns make a second writer fail; commit_verification then retries on the new head.
_commit_lock = asyncio.Lock()
MAX_COMMIT_ATTEMPTS = 25  # many writers can collide on one head; each loses at most a few times with the backoff below
COMMIT_BACKOFF_SECONDS = 0.004  # random wait of up to attempt * this, so colliding writers stop retrying in lockstep

# Every committed head is appended here. The audit compares the database to it, so deleting
# the last rows is detected. Empty string disables it.
# shortcut: a plain file next to the database; anyone who can edit both can rewrite both.
# Copy it to storage the database admin cannot write (or publish the head) before real use.
ANCHOR_PATH = os.getenv("LEDGER_ANCHOR_PATH", str(BACKEND_DIR / "ledger_anchor.jsonl"))

MAX_AUDIT_ERRORS = 100
AUDIT_BATCH_SIZE = 500


class LedgerConflictError(RuntimeError):
    """The chain head kept moving; the commit gave up after MAX_COMMIT_ATTEMPTS."""


def payload_for(record: Any) -> Dict[str, Any]:
    """The exact data that is hashed. Commit and audit both call this, so they cannot disagree."""
    payload = {
        "media_id": str(record.media_reference_id),
        "file_hash": str(record.file_hash),
        "score": f"{record.composite_score:.2f}",
        "risk": str(record.risk_category),
        "action": str(record.enforcement_action),
        "telemetry": record.signal_telemetry,
    }
    if record.hash_version >= 2:
        payload["seq"] = record.seq
        payload["created_at"] = record.created_at.isoformat(timespec="microseconds")
        payload["versions"] = record.versions or {}
    return payload


async def _get_head(db: AsyncSession) -> Tuple[int, str]:
    result = await db.execute(
        select(VerificationRecord.seq, VerificationRecord.current_hash)
        .order_by(VerificationRecord.seq.desc())
        .limit(1)
    )
    row = result.first()
    return (row[0], row[1]) if row else (0, GENESIS_HASH)


async def get_latest_hash(db: AsyncSession) -> str:
    """Hash of the current head of the chain, or GENESIS_HASH when empty."""
    return (await _get_head(db))[1]


def _append_anchor(record: VerificationRecord) -> None:
    if not ANCHOR_PATH:
        return
    line = json.dumps({"seq": record.seq, "hash": record.current_hash, "at": record.created_at.isoformat()})
    try:
        with open(ANCHOR_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        # The row is already committed; losing the anchor weakens truncation detection only.
        logger.exception("Could not write ledger anchor for seq %s", record.seq)


def load_anchors() -> Dict[int, str]:
    if not ANCHOR_PATH or not os.path.exists(ANCHOR_PATH):
        return {}
    anchors: Dict[int, str] = {}
    with open(ANCHOR_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                anchors[int(entry["seq"])] = str(entry["hash"])
            except (ValueError, KeyError, TypeError):
                continue  # a torn last line must not break the audit
    return anchors


async def commit_verification(
    db: AsyncSession,
    media_id: str,
    file_hash: str,
    score: float,
    risk: str,
    action: str,
    telemetry: dict,
    versions: Optional[dict] = None,
) -> VerificationRecord:
    """Append one record to the hash chain and return it."""
    async with _commit_lock:
        for attempt in range(1, MAX_COMMIT_ATTEMPTS + 1):
            head_seq, previous_hash = await _get_head(db)
            record = VerificationRecord(
                seq=head_seq + 1,
                media_reference_id=media_id,
                file_hash=file_hash,
                composite_score=score,
                risk_category=risk,
                enforcement_action=action,
                signal_telemetry=telemetry,
                versions=versions or {},
                hash_version=CURRENT_HASH_VERSION,
                previous_hash=previous_hash,
                created_at=utcnow(),
            )
            record.current_hash = calculate_ledger_hash(previous_hash, payload_for(record))

            db.add(record)
            try:
                await db.commit()
            except IntegrityError:
                # Another process extended the chain first. Read the new head and try again.
                await db.rollback()
                await asyncio.sleep(random.uniform(0, COMMIT_BACKOFF_SECONDS * attempt))
                continue
            except SQLAlchemyError:
                await db.rollback()
                raise

            await db.refresh(record)
            _append_anchor(record)
            return record

    raise LedgerConflictError("Ledger head kept changing; commit abandoned")


def _verify_batch(
    records: List[VerificationRecord], previous_hash: str, expected_seq: int, anchors: Dict[int, str]
) -> Tuple[str, int, List[str]]:
    """CPU-bound: recompute hashes for one batch. Returns (last hash, next seq, errors)."""
    errors: List[str] = []
    for r in records:
        if r.seq != expected_seq:
            errors.append(f"Row {r.id}: sequence gap (expected {expected_seq}, found {r.seq})")
            expected_seq = r.seq
        if r.previous_hash != previous_hash:
            errors.append(f"Row {r.id} (seq {r.seq}): previous_hash does not match the chain")
        if r.hash_version not in (1, CURRENT_HASH_VERSION):
            errors.append(f"Row {r.id} (seq {r.seq}): unknown hash_version {r.hash_version}")
        elif calculate_ledger_hash(r.previous_hash, payload_for(r)) != r.current_hash:
            errors.append(f"Row {r.id} (seq {r.seq}) tampered: hash does not match its data")
        if r.seq in anchors and anchors[r.seq] != r.current_hash:
            errors.append(f"Row {r.id} (seq {r.seq}): hash differs from the anchored hash")
        previous_hash = r.current_hash
        expected_seq += 1
    return previous_hash, expected_seq, errors


async def audit_chain(db: AsyncSession) -> Dict[str, Any]:
    """Walk the whole chain in batches, check every hash, and compare with the anchor file."""
    anchors = load_anchors()
    previous_hash, expected_seq = GENESIS_HASH, 1
    errors: List[str] = []
    length, last_seq = 0, 0

    while True:
        result = await db.execute(
            select(VerificationRecord)
            .where(VerificationRecord.seq > last_seq)
            .order_by(VerificationRecord.seq.asc())
            .limit(AUDIT_BATCH_SIZE)
            .execution_options(populate_existing=True)  # never trust rows cached in this session
        )
        batch = result.scalars().all()
        if not batch:
            break
        previous_hash, expected_seq, batch_errors = await asyncio.to_thread(
            _verify_batch, batch, previous_hash, expected_seq, anchors
        )
        errors.extend(batch_errors)
        length += len(batch)
        last_seq = batch[-1].seq

    truncated = [s for s in anchors if s > last_seq]
    if truncated:
        errors.append(
            f"Chain truncated: anchor records seq {max(truncated)} but the database ends at seq {last_seq}"
        )

    return {
        "ledger_intact": not errors,
        "chain_length": length,
        "errors": errors[:MAX_AUDIT_ERRORS],
        "errors_total": len(errors),
        "anchor_head_seq": max(anchors) if anchors else None,
    }


async def prove(db: AsyncSession, record: VerificationRecord) -> Dict[str, Any]:
    """Evidence that one row is part of an unbroken chain, for the verify page."""
    previous = None
    if record.seq > 1:
        previous = (await db.execute(
            select(VerificationRecord).where(VerificationRecord.seq == record.seq - 1)
            .execution_options(populate_existing=True)
        )).scalars().first()
    head_seq = (await _get_head(db))[0]
    anchors = load_anchors()

    hash_valid = record.hash_version in (1, CURRENT_HASH_VERSION) and (
        calculate_ledger_hash(record.previous_hash, payload_for(record)) == record.current_hash
    )
    if record.seq == 1:
        links_to_previous = record.previous_hash == GENESIS_HASH
    else:
        links_to_previous = previous is not None and previous.current_hash == record.previous_hash

    if not anchors:
        anchored = "no_anchor_file"
    else:
        anchored = "yes" if anchors.get(record.seq) == record.current_hash else (
            "mismatch" if record.seq in anchors else "not_anchored")

    return {
        "id": record.id,
        "seq": record.seq,
        "hash_version": record.hash_version,
        "current_hash": record.current_hash,
        "previous_hash": record.previous_hash,
        "hash_valid": hash_valid,
        "links_to_previous": links_to_previous,
        "anchored": anchored,
        "chain_head_seq": head_seq,
        "verified": hash_valid and links_to_previous and anchored in ("yes", "no_anchor_file", "not_anchored"),
    }


# ---- human review: a decision is a new ledger row, never an edit ----

REVIEWABLE_ACTIONS = ("MANUAL_REVIEW", "FLAG")
REVIEW_CATEGORY = "REVIEWED"


def review_target(record: Any) -> Optional[str]:
    """Id of the row a review row decides on, or None when the row is not a review."""
    if record.risk_category != REVIEW_CATEGORY:
        return None
    return ((record.signal_telemetry or {}).get("_review") or {}).get("of")


async def reviewed_ids(db: AsyncSession) -> set:
    rows = (await db.execute(
        select(VerificationRecord.signal_telemetry).where(VerificationRecord.risk_category == REVIEW_CATEGORY)
    )).scalars().all()
    return {((t or {}).get("_review") or {}).get("of") for t in rows}


async def commit_review(
    db: AsyncSession, original: VerificationRecord, decision: str, note: str, reviewer: str
) -> VerificationRecord:
    action = "HUMAN_APPROVE" if decision == "approve" else "HUMAN_REJECT"
    return await commit_verification(
        db, original.media_reference_id, original.file_hash, original.composite_score or 0.0,
        REVIEW_CATEGORY, action,
        {"_review": {"of": original.id, "decision": decision, "note": note, "reviewer": reviewer}},
        versions={"pipeline": "review"},
    )
