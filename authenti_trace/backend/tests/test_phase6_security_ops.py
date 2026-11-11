import io
import time

import pytest
import pytest_asyncio
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers
from fastapi import UploadFile

from app import metrics, security
from app.database.database import get_db
from app.main import app
from app.models.ledger import Base
from app.services import media_service, verification_service
from app.services.ledger_service import commit_verification
from app.signals.base import ISignalPlugin
from app.schemas.verification import SignalResult


def png(size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (1, 2, 3)).save(buf, "PNG")
    return buf.getvalue()


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine)
    await engine.dispose()


@pytest.fixture
def client(factory, tmp_path, monkeypatch):
    """The real app with all its routers and dependencies, on a throwaway database."""
    security.limiter.hits.clear()
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    security.limiter.hits.clear()


PROTECTED_GETS = ["/api/v1/dashboard/metrics", "/api/v1/dashboard/audit", "/api/v1/dashboard/quality",
                  "/api/v1/reports/x", "/api/v1/reports/x/proof", "/api/v1/reports/by-hash/" + "a" * 64,
                  "/api/v1/jobs/x", "/api/v1/reviews/pending", "/api/v1/ops/metrics"]


# ---- authentication ----

def test_everything_but_health_needs_a_key_when_keys_are_configured(client, monkeypatch):
    monkeypatch.setenv("API_KEYS", "alice:key-one,bob:key-two")
    for path in PROTECTED_GETS:
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={"X-API-Key": "wrong"}).status_code == 401, path
    assert client.post("/api/v1/jobs/", files={"file": ("a.png", png(), "image/png")}).status_code == 401
    assert client.post("/api/v1/upload/", files={"file": ("a.png", png(), "image/png")}).status_code == 401
    assert client.post("/api/v1/reviews/x", json={"decision": "approve"}).status_code == 401

    assert client.get("/api/v1/health").json() == {"status": "ok"}  # public on purpose
    assert client.get("/api/v1/dashboard/metrics", headers={"X-API-Key": "key-two"}).status_code == 200
    assert client.get("/api/v1/dashboard/metrics", headers={"X-API-Key": "key-one"}).status_code == 200


def test_without_keys_the_api_is_open_for_local_development(client, monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    assert client.get("/api/v1/dashboard/metrics").status_code == 200
    assert security.auth_enabled() is False


def test_key_parsing():
    assert security._parse_keys("alice:k1, bob:k2 ,") == {"k1": "alice", "k2": "bob"}
    assert security._parse_keys("plainkey") == {"plainkey": "key1"}
    assert security._parse_keys("") == {}


@pytest.mark.asyncio
async def test_reviewer_identity_comes_from_the_key_not_the_request(factory, client, monkeypatch):
    async with factory() as db:
        row = await commit_verification(db, "m", "h" * 64, 55.0, "UNKNOWN", "MANUAL_REVIEW", {})
        ledger_id = row.id
    monkeypatch.setenv("API_KEYS", "alice:key-one")
    r = client.post(f"/api/v1/reviews/{ledger_id}", headers={"X-API-Key": "key-one"},
                    json={"decision": "approve", "reviewer": "mallory"})
    assert r.status_code == 201
    assert r.json()["signal_telemetry"]["_review"]["reviewer"] == "alice"


# ---- rate limits ----

def test_sliding_window_limiter():
    lim = security.SlidingWindowLimiter()
    assert [lim.check("a", 2, now=t) for t in (0.0, 1.0)] == [None, None]
    assert lim.check("a", 2, now=2.0) == 59           # blocked until the first hit leaves the window
    assert lim.check("b", 2, now=2.0) is None          # other callers are separate
    assert lim.check("a", 2, now=61.0) is None         # window moved on
    assert lim.check("a", 0, now=0.0) is None          # 0 disables the limit


def test_uploads_are_limited_per_caller_and_say_when_to_retry(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_MINUTE", "2")
    monkeypatch.setattr("app.api.v1.endpoints.jobs.enqueue", lambda job_id: None)
    send = lambda: client.post("/api/v1/jobs/", files={"file": ("a.png", png(), "image/png")})  # noqa: E731
    assert [send().status_code, send().status_code] == [202, 202]
    third = send()
    assert third.status_code == 429 and int(third.headers["Retry-After"]) >= 1
    assert client.get("/api/v1/dashboard/metrics").status_code == 200  # other endpoints are not affected


def test_general_limit_applies_to_reads(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
    codes = [client.get("/api/v1/dashboard/metrics").status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


# ---- upload content checks ----

def upload(data: bytes, content_type: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="f", headers=Headers({"content-type": content_type}))


@pytest.mark.parametrize("ctype,head,ok", [
    ("image/jpeg", b"\xff\xd8\xff\xe0" + b"\0" * 12, True),
    ("image/png", b"\x89PNG\r\n\x1a\n" + b"\0" * 8, True),
    ("image/webp", b"RIFF\x00\x00\x00\x00WEBP\x00\x00\x00\x00", True),
    ("video/mp4", b"\x00\x00\x00\x18ftypmp42" + b"\0" * 4, True),
    ("audio/mpeg", b"ID3\x04" + b"\0" * 12, True),
    ("audio/mpeg", b"\xff\xfb\x90\x00" + b"\0" * 12, True),
    ("image/png", b"<html><script>alert(1)</script>", False),
    ("image/jpeg", b"\x89PNG\r\n\x1a\n" + b"\0" * 8, False),
    ("video/mp4", b"MZ\x90\x00" + b"\0" * 12, False),
    ("audio/mpeg", b"\x00\x00\x00\x00", False),
    ("application/pdf", b"%PDF-1.7", False),
])
def test_declared_type_must_match_the_bytes(ctype, head, ok):
    assert media_service.matches_declared_type(ctype, head) is ok


@pytest.mark.asyncio
async def test_html_sent_as_a_png_is_rejected_and_not_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        await media_service.save_upload_and_hash(upload(b"<html>nope</html>", "image/png"))
    assert exc.value.status_code == 415 and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_oversized_image_dimensions_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(media_service, "MAX_IMAGE_PIXELS", 50)
    with pytest.raises(HTTPException) as exc:
        await media_service.save_upload_and_hash(upload(png((20, 20)), "image/png"))
    assert exc.value.status_code == 422 and list(tmp_path.iterdir()) == []
    _, path, _ = await media_service.save_upload_and_hash(upload(png((5, 5)), "image/png"))
    assert path.endswith(".png")


@pytest.mark.asyncio
async def test_png_header_with_garbage_is_not_an_image(tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    with pytest.raises(HTTPException) as exc:
        await media_service.save_upload_and_hash(upload(b"\x89PNG\r\n\x1a\n" + b"garbage" * 20, "image/png"))
    assert exc.value.status_code == 415 and list(tmp_path.iterdir()) == []


# ---- health and metrics ----

class OkSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "OkSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        return SignalResult(plugin_name="OkSignal", score=90.0, confidence=0.9, reasoning="ok")


@pytest.mark.asyncio
async def test_pipeline_records_verdict_and_latency_metrics(monkeypatch):
    metrics.reset()
    monkeypatch.setattr(verification_service, "PLUGINS", [OkSignal()])
    await verification_service.analyze_media("p", "h")
    text = metrics.render({})
    assert 'authentitrace_verdicts_total{action="MANUAL_REVIEW"} 1' in text  # 0.9 evidence is under the minimum
    assert 'authentitrace_signal_seconds_count{signal="OkSignal"} 1' in text


@pytest.mark.asyncio
async def test_ops_metrics_endpoint_reports_queue_and_ledger_gauges(factory, client, isolated_anchor):
    async with factory() as db:
        await commit_verification(db, "m", "h" * 64, 80.0, "LOW_RISK", "APPROVE", {})
    time.sleep(0.01)
    body = client.get("/api/v1/ops/metrics").text
    assert 'authentitrace_jobs{status="queued"} 0' in body
    assert "authentitrace_ledger_head_seq 1" in body
    assert "authentitrace_anchor_age_seconds " in body and "authentitrace_anchor_age_seconds -1" not in body
