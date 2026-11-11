import io
import hashlib
import pytest
import numpy as np
import cv2
from PIL import Image, ExifTags
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.database import Base
from app.signals.heuristic_signals import ContentSignal, RealitySignal, BehavioralSignal, NetworkSignal
from app.signals.registry import registries
from app.signals.integrity import IntegritySignal
from app.services.verification_service import process_verification

@pytest.fixture
def sample_real_image(tmp_path):
    """Generates a sample textured image with camera EXIF tags simulating physical capture."""
    file_path = str(tmp_path / "camera_photo.jpg")
    x = np.linspace(50, 200, 128, dtype=np.uint8)
    y = np.linspace(50, 200, 128, dtype=np.uint8)
    xx, yy = np.meshgrid(x, y)
    arr = np.stack([xx, yy, (xx // 2 + yy // 2)], axis=-1).astype(np.uint8)
    img = Image.fromarray(arr)
    
    exif = img.getexif()
    exif[ExifTags.Base.Make] = "Apple"
    exif[ExifTags.Base.Model] = "iPhone 15 Pro"
    img.save(file_path, "JPEG", exif=exif)
    
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    return file_path, file_hash

@pytest.fixture
def sample_web_image_no_exif(tmp_path):
    """Generates a normal real photo with stripped EXIF (simulating WhatsApp/Twitter download)."""
    file_path = str(tmp_path / "web_download.jpg")
    x = np.linspace(80, 220, 128, dtype=np.uint8)
    y = np.linspace(80, 220, 128, dtype=np.uint8)
    xx, yy = np.meshgrid(x, y)
    arr = np.stack([xx, yy, (xx // 3 + 2 * yy // 3)], axis=-1).astype(np.uint8)
    img = Image.fromarray(arr)
    img.save(file_path, "JPEG", quality=85)
    
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    return file_path, file_hash

@pytest.fixture
def sample_ai_image(tmp_path):
    """Generates a sample image with an AI software generator tag."""
    file_path = str(tmp_path / "ai_generated.png")
    img = Image.new("RGB", (128, 128), color=(200, 100, 50))
    exif = img.getexif()
    exif[ExifTags.Base.Software] = "Stable Diffusion v2.1"
    img.save(file_path, "PNG", exif=exif)
    
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    return file_path, file_hash

@pytest.fixture
def sample_c2pa_image(tmp_path):
    """Generates a sample image with a C2PA JUMBF marker injected into the header."""
    file_path = str(tmp_path / "c2pa_provenance.jpg")
    buf = io.BytesIO()
    img = Image.new("RGB", (128, 128), color=(50, 180, 100))
    img.save(buf, "JPEG")
    raw = buf.getvalue()
    modified_raw = raw[:10] + b"c2pa_provenance_manifest_jumbf" + raw[10:]
    with open(file_path, "wb") as f:
        f.write(modified_raw)
    
    file_hash = hashlib.sha256(modified_raw).hexdigest()
    return file_path, file_hash

@pytest.fixture
def sample_video(tmp_path):
    """Generates a 2-second synthetic video with a sinusoidal cardiac pulse wave."""
    file_path = str(tmp_path / "test_pulse.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(file_path, fourcc, 30.0, (64, 64))
    for i in range(60):
        t = i / 30.0
        val = int(128 + 20 * np.sin(2 * np.pi * 1.2 * t))
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :, 1] = val
        out.write(frame)
    out.release()
    
    with open(file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    return file_path, file_hash

@pytest.mark.asyncio
async def test_content_signal_natural_decay(sample_real_image):
    file_path, file_hash = sample_real_image
    signal = ContentSignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "ContentSignal"
    assert result.score >= 85.0
    assert 0.0 <= result.confidence <= 1.0
    assert "ela_mean" in result.metadata
    assert "sensor_noise_var" in result.metadata
    assert "high_energy_ratio" in result.metadata

@pytest.mark.asyncio
async def test_reality_signal_camera_exif(sample_real_image):
    file_path, file_hash = sample_real_image
    signal = RealitySignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "RealitySignal"
    assert result.score == 92.0
    assert result.metadata["camera_make"] == "Apple"
    assert result.metadata["camera_model"] == "iPhone 15 Pro"

@pytest.mark.asyncio
async def test_reality_signal_web_media_no_false_alarm(sample_web_image_no_exif):
    """Crucial Test: Images from WhatsApp/Twitter with stripped EXIF must NOT be flagged as suspicious!"""
    file_path, file_hash = sample_web_image_no_exif
    signal = RealitySignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "RealitySignal"
    assert result.score >= 80.0  # Clean neutral score
    assert "Standard digital media profile" in result.reasoning
    assert result.metadata["camera_make"] is None

@pytest.mark.asyncio
async def test_reality_signal_ai_software_detected(sample_ai_image):
    file_path, file_hash = sample_ai_image
    signal = RealitySignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "RealitySignal"
    assert result.score == 10.0
    assert "Stable Diffusion" in result.reasoning

@pytest.mark.asyncio
async def test_reality_signal_c2pa_marker(sample_c2pa_image):
    file_path, file_hash = sample_c2pa_image
    signal = RealitySignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "RealitySignal"
    # Marker bytes can be forged, so they must never count as verified provenance.
    assert result.score == 60.0 and result.confidence == 0.30
    assert result.metadata["c2pa_detected"] is True and result.metadata["c2pa_verified"] is False

@pytest.mark.asyncio
async def test_behavioral_signal_optical_coherence(sample_real_image):
    file_path, file_hash = sample_real_image
    signal = BehavioralSignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "BehavioralSignal"
    assert "focus_variance" in result.metadata
    assert result.score >= 80.0

@pytest.mark.asyncio
async def test_behavioral_signal_video_rppg(sample_video):
    file_path, file_hash = sample_video
    signal = BehavioralSignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "BehavioralSignal"
    assert result.metadata["frame_count"] == 60
    assert result.metadata["fps"] == 30.0
    assert result.metadata["pulse_detected"] is True
    assert 45.0 <= result.metadata["detected_bpm"] <= 180.0
    assert result.score == 92.0

@pytest.mark.asyncio
async def test_network_signal_dhash(sample_real_image):
    file_path, file_hash = sample_real_image
    signal = NetworkSignal()
    result = await signal.analyze(file_path, file_hash)
    
    assert result.plugin_name == "NetworkSignal"
    assert "dhash_hex" in result.metadata
    assert len(result.metadata["dhash_hex"]) == 16  # 64-bit hex
    assert result.metadata["registry_hit"] is False
    # Empty registry: no evidence, so zero weight (it must not push the score up)
    assert result.metadata["registry_loaded"] is False and result.confidence == 0.0

@pytest.mark.asyncio
async def test_network_signal_matches_near_duplicates_in_registry(sample_real_image, monkeypatch):
    file_path, file_hash = sample_real_image
    first = await NetworkSignal().analyze(file_path, file_hash)
    known = int(first.metadata["dhash_hex"], 16) ^ 0b101  # 2 bits away from the image's fingerprint
    monkeypatch.setattr(registries, "synthetic_dhash", {f"{known:016x}"})

    hit = await NetworkSignal().analyze(file_path, file_hash)
    assert hit.metadata["registry_hit"] is True and hit.score == 20.0 and hit.metadata["nearest_distance"] == 2

    monkeypatch.setattr(registries, "synthetic_dhash", {f"{known ^ ((1 << 40) - 1):016x}"})  # far away
    miss = await NetworkSignal().analyze(file_path, file_hash)
    assert miss.metadata["registry_hit"] is False and miss.confidence == 0.5

@pytest.mark.asyncio
async def test_integrity_signal_verification(sample_real_image):
    file_path, file_hash = sample_real_image
    signal = IntegritySignal()
    
    # Empty registry: nothing was checked, so the signal must carry no weight.
    empty = await signal.analyze(file_path, file_hash)
    assert empty.confidence == 0.0 and empty.metadata["registry_loaded"] is False

    # Registry loaded and the hash is not in it: weak positive evidence only.
    registries.malicious_sha256 = {"some-other-hash"}
    try:
        result_valid = await signal.analyze(file_path, file_hash)
    finally:
        registries.malicious_sha256 = set()
    assert result_valid.score == 100.0 and result_valid.confidence == 0.6

@pytest.mark.asyncio
async def test_end_to_end_verification_pipeline_clean_photo(sample_real_image):
    file_path, file_hash = sample_real_image
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        report = await process_verification(
            db=session,
            media_id="test-media-123",
            file_path=file_path,
            file_hash=file_hash
        )
        
        assert report.media_reference_id == "test-media-123"
        assert report.file_hash == file_hash
        # Clean camera photo must score HIGH trust (LOW_RISK)
        assert report.composite_score >= 88.0
        assert report.risk_category == "LOW_RISK"
        assert report.enforcement_action == "APPROVE"
        
        # Verify physical invariant telemetry is recorded
        assert "ela_mean" in report.signal_telemetry["ContentSignal"]["metadata"]
        assert "bayer_peak_ratio" in report.signal_telemetry["RealitySignal"]["metadata"]
        assert "focus_variance" in report.signal_telemetry["BehavioralSignal"]["metadata"]
        assert report.signal_telemetry["RealitySignal"]["metadata"]["camera_make"] == "Apple"
        
    await engine.dispose()

@pytest.mark.asyncio
async def test_end_to_end_verification_pipeline_web_photo_no_false_alarm(sample_web_image_no_exif):
    """Crucial E2E Test: A web photo with stripped EXIF must PASS with LOW_RISK / APPROVE."""
    file_path, file_hash = sample_web_image_no_exif
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        report = await process_verification(
            db=session,
            media_id="test-web-media",
            file_path=file_path,
            file_hash=file_hash
        )
        
        # Must be LOW_RISK (no false positive accusation on standard web photos!)
        assert report.composite_score >= 85.0
        assert report.risk_category == "LOW_RISK"
        assert report.enforcement_action == "APPROVE"
        
    await engine.dispose()
