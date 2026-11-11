import asyncio
import os

import boto3
import pytest
import pytest_asyncio
from moto import mock_aws
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import celery_app as celery_module
from app.models.ledger import Base, VerificationJob, VerificationRecord, utcnow
from app.schemas.verification import SignalResult
from app.services import job_runner, verification_service
from app.services.object_store import LocalStore, S3Store
from app.signals.base import ISignalPlugin


class OkSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "OkSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        return SignalResult(plugin_name="OkSignal", score=90.0, confidence=0.9, reasoning="ok")


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine, expire_on_commit=False)
    await engine.dispose()


async def add_job(factory, key, job_id="j1", status="queued"):
    async with factory() as db:
        db.add(VerificationJob(id=job_id, status=status, media_id="m1", file_path=str(key), file_hash="h1", attempts=0))
        await db.commit()


async def rows(factory):
    async with factory() as db:
        return (await db.execute(select(VerificationRecord))).scalars().all()


# ---- object stores ----

def test_local_store_is_a_no_op_wrapper(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    s = LocalStore()
    assert s.put(str(f)) == str(f) and s.fetch(str(f)) == str(f) and s.exists(str(f))
    s.delete(str(f))
    assert not s.exists(str(f))


@pytest.fixture
def s3(tmp_path, monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket="media")
        yield S3Store("media", prefix="uploads", cache_dir=str(tmp_path / "cache"))


def test_s3_store_roundtrip(s3, tmp_path):
    f = tmp_path / "pic.jpg"
    f.write_bytes(b"image-bytes")
    key = s3.put(str(f))
    assert key == "uploads/pic.jpg" and s3.exists(key) and not s3.exists("uploads/nope.jpg")
    assert open(s3.fetch(key), "rb").read() == b"image-bytes"
    s3.delete(key)
    assert not s3.exists(key)


@pytest.mark.asyncio
async def test_job_runs_from_s3_and_removes_its_local_copy(s3, factory, tmp_path, monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    monkeypatch.setattr(job_runner, "store", s3)
    f = tmp_path / "pic.jpg"
    f.write_bytes(b"image-bytes")
    key = s3.put(str(f))
    await add_job(factory, key)

    await job_runner.run_job("j1", factory)

    assert len(await rows(factory)) == 1
    assert os.listdir(s3.cache_dir) == []  # local cache copy deleted
    assert s3.exists(key)  # the object stays for the bucket lifecycle rule


# ---- claiming, recovery, celery ----

@pytest.mark.asyncio
async def test_two_runners_on_one_job_write_one_ledger_row(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    f = tmp_path / "m.png"
    f.write_bytes(b"x")
    await add_job(factory, f)
    await asyncio.gather(job_runner.run_job("j1", factory), job_runner.run_job("j1", factory))
    assert len(await rows(factory)) == 1


@pytest.mark.asyncio
async def test_recovery_requeues_abandoned_running_jobs(factory, tmp_path, monkeypatch):
    queued = []
    monkeypatch.setattr(job_runner, "SessionLocal", factory)
    monkeypatch.setattr(job_runner, "enqueue", queued.append)
    await add_job(factory, tmp_path / "a", "running-job", status="running")
    await add_job(factory, tmp_path / "b", "queued-job", status="queued")
    await add_job(factory, tmp_path / "c", "done-job", status="done")

    assert await job_runner.recover_jobs() == 2  # no broker: a running job died with the process
    assert sorted(queued) == ["queued-job", "running-job"]


@pytest.mark.asyncio
async def test_recovery_with_a_broker_leaves_fresh_running_jobs_alone(factory, tmp_path, monkeypatch):
    queued = []
    monkeypatch.setattr(job_runner, "SessionLocal", factory)
    monkeypatch.setattr(job_runner, "enqueue", queued.append)
    monkeypatch.setattr(job_runner, "BROKER_URL", "redis://x")
    await add_job(factory, tmp_path / "a", "fresh", status="running")
    await add_job(factory, tmp_path / "b", "stale", status="running")
    async with factory() as db:
        await db.execute(update(VerificationJob).where(VerificationJob.id == "stale")
                         .values(updated_at=utcnow().replace(year=2020)))
        await db.commit()

    await job_runner.recover_jobs()
    assert queued == ["stale"]


def test_enqueue_uses_celery_when_a_broker_is_configured(monkeypatch):
    sent = []

    class Fake:
        @staticmethod
        def delay(job_id):
            sent.append(job_id)

    monkeypatch.setattr(job_runner, "BROKER_URL", "redis://x")
    monkeypatch.setattr(job_runner, "verify_job", Fake)
    job_runner.enqueue("abc")  # no event loop needed on the Celery path
    assert sent == ["abc"]


def test_celery_task_runs_a_job_end_to_end(tmp_path, monkeypatch):
    """Eager mode runs the real task body (own event loop, own engine) without a broker."""
    db_file = tmp_path / "c.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    media = tmp_path / "m.png"
    media.write_bytes(b"x")

    async def setup():
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        f = async_sessionmaker(bind=engine, expire_on_commit=False)
        await add_job(f, media)
        await engine.dispose()

    async def count():
        engine = create_async_engine(url)
        f = async_sessionmaker(bind=engine, expire_on_commit=False)
        n = len(await rows(f))
        await engine.dispose()
        return n

    asyncio.run(setup())
    monkeypatch.setattr(celery_module.database, "SQLALCHEMY_DATABASE_URL", url)
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    monkeypatch.setattr(celery_module.celery_app.conf, "task_always_eager", True)

    celery_module.verify_job.delay("j1").get()
    assert asyncio.run(count()) == 1
