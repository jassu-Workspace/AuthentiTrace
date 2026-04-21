import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.models.ledger import Base, VerificationRecord
from app.services.ledger_service import commit_verification, get_latest_hash, GENESIS_HASH
from app.utils.security import calculate_ledger_hash

import pytest_asyncio
# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    
    async with TestingSessionLocal() as session:
        yield session
        
    await engine.dispose()

@pytest.mark.asyncio
async def test_ledger_genesis(test_db):
    """Test that an empty ledger returns the GENESIS_HASH."""
    latest_hash = await get_latest_hash(test_db)
    assert latest_hash == GENESIS_HASH

@pytest.mark.asyncio
async def test_ledger_chaining(test_db):
    """Test that multiple commits link their hashes correctly."""
    record1 = await commit_verification(
        test_db, "media_1", "hash_1", 90.0, "LOW_RISK", "APPROVE", {"data": "test1"}
    )
    
    assert record1.previous_hash == GENESIS_HASH
    assert record1.current_hash != GENESIS_HASH
    
    record2 = await commit_verification(
        test_db, "media_2", "hash_2", 80.0, "LOW_RISK", "APPROVE", {"data": "test2"}
    )
    
    assert record2.previous_hash == record1.current_hash
    assert record2.current_hash != record1.current_hash

@pytest.mark.asyncio
async def test_tamper_detection(test_db):
    """Test that tampering with a historical record explicitly breaks the chain verification."""
    
    # 1. Add records
    r1 = await commit_verification(test_db, "media_1", "abc", 50.0, "MEDIUM_RISK", "FLAG", {})
    r2 = await commit_verification(test_db, "media_2", "def", 50.0, "MEDIUM_RISK", "FLAG", {})
    
    # Simulate the Dashboard Audit logic
    payload = {
        "media_id": str(r1.media_reference_id),
        "file_hash": str(r1.file_hash),
        "score": f"{r1.composite_score:.2f}",
        "risk": str(r1.risk_category),
        "action": str(r1.enforcement_action),
        "telemetry": r1.signal_telemetry
    }
    
    # Verify it matches mathematically initially
    expected_hash = calculate_ledger_hash(r1.previous_hash, payload)
    assert expected_hash == r1.current_hash
    
    # 2. Simulate a Rogue DBA doing a direct SQL update to modify the score
    await test_db.execute(
        text(f"UPDATE verification_ledger SET composite_score = 99.0 WHERE id = '{r1.id}'")
    )
    await test_db.commit()
    
    # Refresh object
    await test_db.refresh(r1)
    
    # 3. Simulate the Dashboard Audit hitting the DB again
    tampered_payload = {
        "media_id": str(r1.media_reference_id),
        "file_hash": str(r1.file_hash),
        "score": f"{r1.composite_score:.2f}",
        "risk": str(r1.risk_category),
        "action": str(r1.enforcement_action),
        "telemetry": r1.signal_telemetry
    }
    
    new_expected_hash = calculate_ledger_hash(r1.previous_hash, tampered_payload)
    
    # The new hash of the row data will NOT MATCH the cryptographically stored current_hash
    assert new_expected_hash != r1.current_hash
