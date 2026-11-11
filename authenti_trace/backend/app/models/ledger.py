import uuid
import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON, Integer, Index
from app.database.database import Base


def utcnow() -> datetime.datetime:
    """Naive UTC time. Stored and hashed in this one form so audits recompute the same bytes."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class VerificationRecord(Base):
    __tablename__ = "verification_ledger"
    # Two writers can never extend the same head: seq and previous_hash are each unique.
    __table_args__ = (
        Index("uq_ledger_seq", "seq", unique=True),
        Index("uq_ledger_previous_hash", "previous_hash", unique=True),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    seq = Column(Integer, nullable=False)  # position in the chain, starts at 1
    media_reference_id = Column(String, index=True)
    file_hash = Column(String, nullable=False)

    # Aggregated results
    composite_score = Column(Float, nullable=True)
    risk_category = Column(String, nullable=True)
    enforcement_action = Column(String, nullable=True)

    # Detailed explainer JSON breakdown
    signal_telemetry = Column(JSON, nullable=True)

    # Which pipeline, thresholds and model produced this row (part of the hash from hash_version 2)
    versions = Column(JSON, nullable=True)
    hash_version = Column(Integer, nullable=False, default=2)

    # Cryptographic ledger linkage
    previous_hash = Column(String, nullable=False)
    current_hash = Column(String, nullable=False)

    created_at = Column(DateTime, default=utcnow)


class VerificationJob(Base):
    """One background verification. Status: queued, running, done, failed."""
    __tablename__ = "verification_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, nullable=False, default="queued", index=True)
    media_id = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_hash = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    report_id = Column(String, nullable=True)  # ledger row id once done
    error = Column(String, nullable=True)  # fixed code, never exception text
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)
