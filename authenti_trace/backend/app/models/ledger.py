import uuid
import datetime
from sqlalchemy import Column, String, Float, DateTime, JSON
from app.database.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class VerificationRecord(Base):
    __tablename__ = "verification_ledger"

    id = Column(String, primary_key=True, default=generate_uuid, index=True)
    media_reference_id = Column(String, index=True)
    file_hash = Column(String, nullable=False)
    
    # Aggregated results
    composite_score = Column(Float, nullable=True)
    risk_category = Column(String, nullable=True)
    enforcement_action = Column(String, nullable=True)
    
    # Detailed explainer JSON breakdown
    signal_telemetry = Column(JSON, nullable=True)
    
    # Cryptographic ledger linkage
    previous_hash = Column(String, nullable=False)
    current_hash = Column(String, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

class SignalWeight(Base):
    __tablename__ = "signals_weight"

    id = Column(String, primary_key=True, default=generate_uuid)
    signal_name = Column(String, unique=True, index=True)
    current_weight = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
