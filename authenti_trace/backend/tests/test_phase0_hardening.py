import io
import os

import pytest
from PIL import Image
import pytest_asyncio
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers

from app.database.database import SQLALCHEMY_DATABASE_URL
from app.models.ledger import Base
from app.schemas.verification import SignalResult
from app.services import media_service, verification_service
from app.services.scoring_engine import calculate_trust_score
from app.signals.base import ISignalPlugin
from app.signals.integrity import IntegritySignal
from app.signals.registry import registries


def png_bytes(size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buf, "PNG")
    return buf.getvalue()


def make_upload(data: bytes, content_type: str, filename: str = "x.png") -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename, headers=Headers({"content-type": content_type}))


def signal(name: str, score: float, confidence: float) -> SignalResult:
    return SignalResult(plugin_name=name, score=score, confidence=confidence, reasoning="t")


# ---- scoring ----

def test_all_zero_confidence_signals_need_manual_review():
    result = calculate_trust_score([signal("A", 50.0, 0.0), signal("B", 50.0, 0.0)], {})
    assert result.risk_category == "UNKNOWN"
    assert result.enforcement_action == "MANUAL_REVIEW"


def test_zero_confidence_signal_does_not_trigger_critical_cap():
    result = calculate_trust_score([signal("A", 95.0, 0.9), signal("B", 0.0, 0.0)], {})
    assert result.trust_score == 95.0


def test_high_confidence_failure_caps_score_at_20():
    result = calculate_trust_score([signal("A", 100.0, 0.95), signal("B", 0.0, 0.95)], {})
    assert result.trust_score <= 20.0


# ---- media service ----

@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(media_service, "STORAGE_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_unsupported_type_returns_415(storage):
    with pytest.raises(HTTPException) as exc:
        await media_service.save_upload_and_hash(make_upload(b"data", "text/html"))
    assert exc.value.status_code == 415
    assert list(storage.iterdir()) == []


@pytest.mark.asyncio
async def test_oversize_returns_413_and_removes_partial_file(storage, monkeypatch):
    monkeypatch.setattr(media_service, "MAX_FILE_SIZE_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        await media_service.save_upload_and_hash(make_upload(png_bytes() + b"x" * 100, "image/png"))
    assert exc.value.status_code == 413
    assert list(storage.iterdir()) == []


@pytest.mark.asyncio
async def test_extension_comes_from_mime_not_filename(storage):
    _, path, _ = await media_service.save_upload_and_hash(
        make_upload(png_bytes(), "image/png", filename="evil.html")
    )
    assert path.endswith(".png")
    assert os.path.dirname(path) == str(storage)


def test_default_paths_do_not_depend_on_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert os.path.isabs(media_service.STORAGE_DIR)
    assert SQLALCHEMY_DATABASE_URL.startswith("sqlite+aiosqlite:///") and os.path.isabs(
        SQLALCHEMY_DATABASE_URL.removeprefix("sqlite+aiosqlite:///")
    )


# ---- integrity ----

@pytest.mark.asyncio
async def test_integrity_blacklist_hit_scores_zero(monkeypatch):
    monkeypatch.setattr(registries, "malicious_sha256", {"bad"})
    result = await IntegritySignal().analyze("ignored", "bad")
    assert result.score == 0.0 and result.metadata["blacklist_hit"] is True


# ---- pipeline: failed plugin ----

class ExplodingSignal(ISignalPlugin):
    @property
    def name(self) -> str:
        return "ExplodingSignal"

    async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
        raise RuntimeError("secret path C:/private/thing")


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_plugin_has_zero_weight_and_no_exception_text(db, monkeypatch):
    class Good(ISignalPlugin):
        @property
        def name(self) -> str:
            return "Good"

        async def analyze(self, media_path: str, file_hash: str) -> SignalResult:
            return signal("Good", 90.0, 0.9)

    monkeypatch.setattr(verification_service, "PLUGINS", [Good(), ExplodingSignal()])
    report = await verification_service.process_verification(db, "m1", "p", "h")

    assert report.composite_score == 90.0  # failed plugin did not drag the score down
    failed = report.signal_telemetry["ExplodingSignal"]
    assert failed["confidence"] == 0.0
    assert failed["metadata"] == {"error": "RuntimeError"}
    assert "secret path" not in str(report.signal_telemetry)
