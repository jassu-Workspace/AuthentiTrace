import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.models.ledger import Base
from app.services.ledger_service import commit_verification, get_latest_hash, GENESIS_HASH
from app.api.v1.endpoints.dashboard import audit_ledger

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
    """A direct SQL edit of a historical row must make the audit fail."""
    r1 = await commit_verification(test_db, "media_1", "abc", 50.0, "MEDIUM_RISK", "FLAG", {})
    await commit_verification(test_db, "media_2", "def", 50.0, "MEDIUM_RISK", "FLAG", {})

    assert (await audit_ledger(test_db))["ledger_intact"] is True

    # Simulate a rogue DBA changing the score directly in the database
    await test_db.execute(
        text("UPDATE verification_ledger SET composite_score = 99.0 WHERE id = :id"), {"id": r1.id}
    )
    await test_db.commit()

    audit = await audit_ledger(test_db)
    assert audit["ledger_intact"] is False
    assert any("tampered" in e for e in audit["errors"])

@pytest.mark.asyncio
async def test_concurrent_commits_chain_integrity():
    """Test that concurrent commit_verification calls serialize cleanly and maintain chain integrity."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

    async def concurrent_task(media_name):
        async with TestingSessionLocal() as session:
            return await commit_verification(
                session, media_name, f"hash_{media_name}", 85.0, "LOW_RISK", "APPROVE", {"task": media_name}
            )

    # Trigger 5 concurrent tasks simultaneously
    records = await asyncio.gather(*[concurrent_task(f"media_{i}") for i in range(5)])

    # Verify no two records have the same current_hash
    current_hashes = [r.current_hash for r in records]
    assert len(set(current_hashes)) == 5

    # Verify audit endpoint produces intact chain
    async with TestingSessionLocal() as session:
        audit_res = await audit_ledger(session)
        assert audit_res["ledger_intact"] is True
        assert audit_res["chain_length"] == 5
        assert len(audit_res["errors"]) == 0

    await engine.dispose()
