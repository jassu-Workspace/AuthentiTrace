import asyncio
import io
import os
import sqlite3
import time

import pytest
from PIL import Image
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints import jobs as jobs_endpoint
from app.api.v1.endpoints.dashboard import get_dashboard_metrics
from app.database.database import get_db
from app.database.migrate import upgrade_to_head
from app.models.ledger import Base, VerificationJob, VerificationRecord
from app.schemas.verification import SignalResult
from app.services import job_runner, ledger_service, media_service, verification_service
from app.services.ledger_service import GENESIS_HASH, audit_chain, commit_verification
from app.services.rescore import rescore_outdated
from app.signals.base import ISignalPlugin
from app.utils.security import calculate_ledger_hash


@pytest_asyncio.fixture
async def factory(tmp_path):
    """File-backed SQLite with a session factory (several sessions can share it, like several processes)."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    await engine.dispose()


_buf = io.BytesIO()
Image.new("RGB", (8, 8)).save(_buf, "PNG")
PNG = _buf.getvalue()


async def add(db, n, **kw):
    return [await commit_verification(db, f"m{i}", f"h{i}", 80.0, "LOW_RISK", "APPROVE", {"i": i}, **kw) for i in range(n)]


# ---- ledger: hash v2, sequence, anchor ----

@pytest.mark.asyncio
async def test_new_rows_use_hash_v2_with_seq_and_versions(factory):
    async with factory() as db:
        a, b = await add(db, 2, versions={"pipeline": "x"})
    assert (a.seq, b.seq) == (1, 2) and a.previous_hash == GENESIS_HASH
    assert a.hash_version == 2 and a.versions == {"pipeline": "x"}


@pytest.mark.asyncio
@pytest.mark.parametrize("sql", [
    "UPDATE verification_ledger SET created_at = '2001-01-01 00:00:00.000000' WHERE seq = 1",
    "UPDATE verification_ledger SET versions = '{\"pipeline\": \"forged\"}' WHERE seq = 1",
    "UPDATE verification_ledger SET composite_score = 1.0 WHERE seq = 1",
])
async def test_audit_detects_edits_to_any_hashed_field(factory, sql):
    async with factory() as db:
        await add(db, 2, versions={"pipeline": "x"})
        assert (await audit_chain(db))["ledger_intact"] is True
        await db.execute(text(sql))
        await db.commit()
        audit = await audit_chain(db)
    assert audit["ledger_intact"] is False


@pytest.mark.asyncio
async def test_audit_detects_deleted_tail_rows_through_the_anchor(factory):
    async with factory() as db:
        await add(db, 3)
        await db.execute(text("DELETE FROM verification_ledger WHERE seq = 3"))
        await db.commit()
        audit = await audit_chain(db)
    assert audit["ledger_intact"] is False
    assert any("truncated" in e for e in audit["errors"])
    assert audit["anchor_head_seq"] == 3


@pytest.mark.asyncio
async def test_audit_detects_deleted_middle_row(factory):
    async with factory() as db:
        await add(db, 3)
        await db.execute(text("DELETE FROM verification_ledger WHERE seq = 2"))
        await db.commit()
        audit = await audit_chain(db)
    assert audit["ledger_intact"] is False
    assert any("sequence gap" in e for e in audit["errors"])


@pytest.mark.asyncio
async def test_audit_works_in_batches(factory, monkeypatch):
    monkeypatch.setattr(ledger_service, "AUDIT_BATCH_SIZE", 2)
    async with factory() as db:
        await add(db, 5)
        audit = await audit_chain(db)
    assert audit["ledger_intact"] is True and audit["chain_length"] == 5


@pytest.mark.asyncio
async def test_writers_without_a_shared_lock_do_not_fork_the_chain(factory, monkeypatch):
    """Simulates separate processes: no shared lock, only the database guard (unique seq and previous_hash)."""
    class NoLock:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(ledger_service, "_commit_lock", NoLock())

    async def writer(i):
        async with factory() as db:
            return await commit_verification(db, f"m{i}", f"h{i}", 80.0, "LOW_RISK", "APPROVE", {"w": i})

    await asyncio.gather(*[writer(i) for i in range(16)])
    async with factory() as db:
        audit = await audit_chain(db)
        seqs = (await db.execute(select(VerificationRecord.seq).order_by(VerificationRecord.seq))).scalars().all()
    assert audit["ledger_intact"] is True and audit["chain_length"] == 16
    assert seqs == list(range(1, 17))


# ---- migration of an old database ----

@pytest.mark.asyncio
async def test_migration_upgrades_a_phase0_database_and_keeps_old_hashes_valid(tmp_path):
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.execute("""CREATE TABLE verification_ledger (
        id VARCHAR PRIMARY KEY, media_reference_id VARCHAR, file_hash VARCHAR NOT NULL, composite_score FLOAT,
        risk_category VARCHAR, enforcement_action VARCHAR, signal_telemetry JSON,
        previous_hash VARCHAR NOT NULL, current_hash VARCHAR NOT NULL, created_at DATETIME)""")
    prev = GENESIS_HASH
    for i in range(3):  # version-1 hashing, exactly as the old code did
        payload = {"media_id": f"m{i}", "file_hash": f"h{i}", "score": "70.00", "risk": "MEDIUM_RISK",
                   "action": "FLAG", "telemetry": {}}
        cur = calculate_ledger_hash(prev, payload)
        conn.execute("INSERT INTO verification_ledger VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (f"id{i}", f"m{i}", f"h{i}", 70.0, "MEDIUM_RISK", "FLAG", "{}", prev, cur,
                      f"2025-01-0{i + 1} 00:00:00.000000"))
        prev = cur
    conn.commit()
    conn.close()

    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    await upgrade_to_head(url)
    await upgrade_to_head(url)  # running twice is safe

    engine = create_async_engine(url)
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as db:
        rows = (await db.execute(select(VerificationRecord).order_by(VerificationRecord.seq))).scalars().all()
        assert [(r.seq, r.hash_version) for r in rows] == [(1, 1), (2, 1), (3, 1)]
        assert (await audit_chain(db))["ledger_intact"] is True

        new = await commit_verification(db, "m9", "h9", 90.0, "LOW_RISK", "APPROVE", {})
        assert (new.seq, new.hash_version, new.previous_hash) == (4, 2, rows[-1].current_hash)
        assert (await audit_chain(db))["ledger_intact"] is True
        assert (await db.execute(select(VerificationJob))).scalars().all() == []  # table exists
    await engine.dispose()


# ---- signals: threads and timeout ----

class SlowSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "SlowSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        time.sleep(0.4)  # blocking CPU-style work
        return SignalResult(plugin_name="SlowSignal", score=90.0, confidence=0.9, reasoning="ok")


@pytest.mark.asyncio
async def test_blocking_signal_does_not_block_the_event_loop(monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [SlowSignal()])
    ticks = 0

    async def ticker():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    signals, scoring = await verification_service.analyze_media("p", "h")
    task.cancel()
    assert ticks >= 15  # a blocked loop would tick about once
    assert signals[0].score == 90.0


@pytest.mark.asyncio
async def test_slow_signal_times_out_with_zero_weight(monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [SlowSignal()])
    monkeypatch.setattr(verification_service, "SIGNAL_TIMEOUT_SECONDS", 0.05)
    signals, scoring = await verification_service.analyze_media("p", "h")
    assert signals[0].confidence == 0.0 and signals[0].metadata == {"error": "TimeoutError"}
    assert scoring.enforcement_action == "MANUAL_REVIEW"


# ---- jobs ----

class OkSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "OkSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        return SignalResult(plugin_name="OkSignal", score=90.0, confidence=0.9, reasoning="ok")


async def make_job(factory, path):
    async with factory() as db:
        db.add(VerificationJob(id="j1", status="queued", media_id="m1", file_path=str(path), file_hash="h1", attempts=0))
        await db.commit()


async def job_state(factory):
    async with factory() as db:
        j = (await db.execute(select(VerificationJob))).scalars().first()
        n = len((await db.execute(select(VerificationRecord))).scalars().all())
        return j.status, j.attempts, j.report_id, j.error, n


@pytest.mark.asyncio
async def test_job_runs_to_done_and_writes_one_ledger_row(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    f = tmp_path / "m.png"
    f.write_bytes(b"x")
    await make_job(factory, f)
    await job_runner.run_job("j1", factory)
    status, attempts, report_id, error, rows = await job_state(factory)
    assert (status, attempts, error, rows) == ("done", 1, None, 1) and report_id


@pytest.mark.asyncio
async def test_failing_job_retries_then_fails_without_a_ledger_row(factory, tmp_path, monkeypatch):
    calls = 0

    async def boom(*a, **k):
        nonlocal calls
        calls += 1
        raise RuntimeError("secret internals")

    monkeypatch.setattr(job_runner, "process_verification", boom)
    f = tmp_path / "m.png"
    f.write_bytes(b"x")
    await make_job(factory, f)
    await job_runner.run_job("j1", factory)
    status, attempts, report_id, error, rows = await job_state(factory)
    assert (status, attempts, report_id, rows) == ("failed", job_runner.MAX_ATTEMPTS, None, 0)
    assert error == "VERIFICATION_FAILED" and "secret" not in error
    assert calls == job_runner.MAX_ATTEMPTS and not f.exists()  # media removed after the final failure


@pytest.mark.asyncio
async def test_job_with_missing_media_fails_without_a_ledger_row(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    await make_job(factory, tmp_path / "gone.png")
    await job_runner.run_job("j1", factory)
    assert await job_state(factory) == ("failed", 0, None, "MEDIA_MISSING", 0)


@pytest.mark.asyncio
async def test_finished_job_is_not_run_twice(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    f = tmp_path / "m.png"
    f.write_bytes(b"x")
    await make_job(factory, f)
    await job_runner.run_job("j1", factory)
    await job_runner.run_job("j1", factory)
    assert (await job_state(factory))[4] == 1


def test_jobs_endpoint_returns_202_and_job_status(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    queued = []
    monkeypatch.setattr(jobs_endpoint, "enqueue", queued.append)

    app = FastAPI()
    app.include_router(jobs_endpoint.router, prefix="/jobs")

    # Same session settings as the app (expire_on_commit defaults to True), unlike the shared test factory
    app_sessions = async_sessionmaker(bind=factory.kw["bind"])

    async def override():
        async with app_sessions() as session:
            yield session

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    r = client.post("/jobs/", files={"file": ("a.png", io.BytesIO(PNG), "image/png")})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued" and queued == [body["job_id"]]

    got = client.get(f"/jobs/{body['job_id']}")
    assert got.status_code == 200 and got.json()["status"] == "queued"
    assert client.get("/jobs/nope").status_code == 404
    assert client.post("/jobs/", files={"file": ("a.html", io.BytesIO(b"x"), "text/html")}).status_code == 415


# ---- metrics, retention, rescore ----

@pytest.mark.asyncio
async def test_metrics_counts_by_risk_in_one_grouped_query(factory):
    async with factory() as db:
        await commit_verification(db, "a", "h", 90.0, "LOW_RISK", "APPROVE", {})
        await commit_verification(db, "b", "h", 90.0, "LOW_RISK", "APPROVE", {})
        await commit_verification(db, "c", "h", 10.0, "HIGH_RISK", "RESTRICT", {})
        m = await get_dashboard_metrics(db)
    assert m == {"total_verifications": 3, "risk_distribution": {"LOW_RISK": 2, "MEDIUM_RISK": 0, "HIGH_RISK": 1, "UNKNOWN": 0}}


def test_purge_removes_only_expired_media(tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    old, new = tmp_path / "old.jpg", tmp_path / "new.jpg"
    old.write_bytes(b"1")
    new.write_bytes(b"2")
    ten_days_ago = time.time() - 10 * 86400
    os.utime(old, (ten_days_ago, ten_days_ago))

    assert media_service.purge_expired_media(retention_days=0) == 0 and old.exists()  # disabled
    assert media_service.purge_expired_media(retention_days=5) == 1
    assert not old.exists() and new.exists()


@pytest.mark.asyncio
async def test_rescore_appends_new_rows_and_skips_missing_or_changed_media(factory, tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])

    good = b"good-bytes"
    (tmp_path / "mA.jpg").write_bytes(good)
    (tmp_path / "mB.jpg").write_bytes(b"changed-after-hashing")
    async with factory() as db:
        a = await commit_verification(db, "mA", hashlib.sha256(good).hexdigest(), 50.0, "MEDIUM_RISK", "FLAG", {},
                                      versions={"pipeline": "old"})
        await commit_verification(db, "mB", "recorded-hash", 50.0, "MEDIUM_RISK", "FLAG", {}, versions={"pipeline": "old"})
        await commit_verification(db, "mC", "h", 50.0, "MEDIUM_RISK", "FLAG", {}, versions={"pipeline": "old"})  # no file

        result = await rescore_outdated(db)
        assert result == {"rescored": 1, "skipped": 2}

        newest = (await db.execute(select(VerificationRecord).order_by(VerificationRecord.seq.desc()))).scalars().first()
        assert newest.media_reference_id == "mA" and newest.versions["rescore_of"] == a.id
        assert newest.versions["pipeline"] == verification_service.VERSIONS["pipeline"]
        assert (await audit_chain(db))["ledger_intact"] is True

        assert (await rescore_outdated(db))["rescored"] == 0  # already current: nothing to do
