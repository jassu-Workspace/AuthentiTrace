import json

import numpy as np
import pytest
from PIL import Image

from app.schemas.verification import SignalResult
from app.services import calibration as cal
from app.services.scoring_engine import calculate_trust_score
from app.services.verification_service import analyze_media
from app.signals import heuristic_signals, registry
from app.signals.heuristic_signals import RealitySignal
from app.signals.provenance import interpret_c2pa, read_c2pa


def sig(name, score, conf):
    return SignalResult(plugin_name=name, score=score, confidence=conf, reasoning="t")


# ---- scoring: abstain instead of guessing ----

def test_too_little_evidence_abstains():
    r = calculate_trust_score([sig("A", 95, 0.6)], {})  # evidence 0.6 < 1.0
    assert (r.risk_category, r.enforcement_action) == ("UNKNOWN", "MANUAL_REVIEW")
    assert "Not enough evidence" in r.reason and r.evidence == 0.6


def test_confident_signals_that_disagree_abstain():
    r = calculate_trust_score([sig("A", 95, 0.9), sig("B", 20, 0.9)], {})
    assert r.enforcement_action == "MANUAL_REVIEW" and "disagree" in r.reason


def test_a_critical_failure_is_not_turned_into_a_review():
    r = calculate_trust_score([sig("A", 95, 0.9), sig("B", 5, 0.99)], {})
    assert r.enforcement_action == "RESTRICT" and r.trust_score <= 20.0


def test_agreeing_confident_signals_decide():
    r = calculate_trust_score([sig("A", 92, 0.9), sig("B", 88, 0.8)], {})
    assert r.enforcement_action == "APPROVE" and r.calibrated is False


def test_calibration_maps_the_raw_score():
    calibration = {"type": "platt", "a": 8.0, "b": -4.0}  # raw 50 -> 50%, raw 100 -> 98%
    r = calculate_trust_score([sig("A", 100, 1.0), sig("B", 100, 1.0)], {}, calibration)
    assert r.calibrated is True and 97 < r.trust_score < 99
    low = calculate_trust_score([sig("A", 20, 1.0), sig("B", 25, 1.0)], {}, calibration)
    assert low.enforcement_action == "RESTRICT"


# ---- calibration and fusion fitting ----

def test_platt_fit_recovers_a_known_curve():
    rng = np.random.default_rng(1)
    scores = rng.uniform(0, 100, 4000)
    p = 1 / (1 + np.exp(-(6.0 * scores / 100 - 3.0)))
    labels = (rng.uniform(size=4000) < p).astype(int)
    a, b = cal.fit_platt(scores, labels)
    assert a == pytest.approx(6.0, abs=0.7) and b == pytest.approx(-3.0, abs=0.5)
    assert cal.apply_platt(50.0, {"a": a, "b": b}) == pytest.approx(50.0, abs=6)


def test_fits_need_both_classes():
    with pytest.raises(ValueError):
        cal.fit_platt([10, 20], [1, 1])
    with pytest.raises(ValueError):
        cal.fit_fusion_weights([{"A": {"score": 90, "confidence": 1}}] * 2, [1, 1])


def test_fusion_gives_the_informative_signal_more_weight():
    rng = np.random.default_rng(2)
    rows, labels = [], []
    for _ in range(600):
        real = int(rng.integers(0, 2))
        rows.append({
            "Good": {"score": 85 if real else 15, "confidence": 0.9},
            "Noise": {"score": float(rng.uniform(0, 100)), "confidence": 0.9},
        })
        labels.append(real)
    w = cal.fit_fusion_weights(rows, labels)
    assert w["Good"] > 3 * w["Noise"]
    assert sum(w.values()) / len(w) == pytest.approx(1.0, abs=0.01)


def test_calibration_files_are_optional(tmp_path):
    assert cal.load_calibration(str(tmp_path / "missing.json")) is None
    assert cal.load_fusion_weights(str(tmp_path / "missing.json")) == (None, None)
    (tmp_path / "f.json").write_text(json.dumps({"weights": {"A": 2}, "version": "v1"}))
    assert cal.load_fusion_weights(str(tmp_path / "f.json")) == ({"A": 2.0}, "v1")


# ---- provenance ----

def test_interpret_c2pa_states():
    ok = interpret_c2pa("Trusted", json.dumps({"active_manifest": "m", "manifests": {"m": {"claim_generator": "Cam/1"}}}))
    assert ok["verified"] and ok["trusted"] and not ok["ai_generated"] and ok["claim_generator"] == "Cam/1"
    assert not interpret_c2pa("Invalid", "{}")["verified"]
    ai = interpret_c2pa("Valid", '{"x": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"}')
    assert ai["ai_generated"] and ai["verified"]
    assert interpret_c2pa("Valid", "not json")["state"] == "Valid"


def test_read_c2pa_is_none_without_a_manifest(tmp_path):
    img = tmp_path / "a.jpg"
    Image.new("RGB", (32, 32)).save(img)
    assert read_c2pa(str(img)) is None
    assert read_c2pa(str(tmp_path / "missing.jpg")) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("info,expected_score", [
    ({"state": "Valid", "verified": True, "trusted": False, "ai_generated": False}, 97.0),
    ({"state": "Trusted", "verified": True, "trusted": True, "ai_generated": False}, 99.0),
    ({"state": "Invalid", "verified": False, "trusted": False, "ai_generated": False}, 15.0),
    ({"state": "Valid", "verified": True, "trusted": False, "ai_generated": True}, 5.0),
])
async def test_reality_signal_uses_the_verified_manifest(tmp_path, monkeypatch, info, expected_score):
    img = tmp_path / "a.jpg"
    Image.new("RGB", (64, 64), (90, 90, 90)).save(img)
    monkeypatch.setattr(heuristic_signals, "read_c2pa", lambda path: info)
    result = await RealitySignal().analyze(str(img), "h")
    assert result.score == expected_score
    assert result.metadata["c2pa_verified"] is info["verified"]


# ---- registries ----

def test_registries_load_files_and_match_by_hamming_distance(tmp_path, monkeypatch):
    (tmp_path / "malicious_sha256.txt").write_text("# comment\nABC123  # trailing note\n\n")
    (tmp_path / "synthetic_dhash.txt").write_text("00000000000000ff\n")
    monkeypatch.setattr(registry, "REGISTRY_DIR", tmp_path)
    r = registry.Registries()
    assert r.malicious_sha256 == {"abc123"}
    assert r.nearest_dhash_distance("00000000000000fe") == 1
    assert r.nearest_dhash_distance("ffffffffffffffff") == 56
    empty = registry.Registries.__new__(registry.Registries)
    empty.synthetic_dhash = set()
    assert empty.nearest_dhash_distance("00") is None


# ---- pipeline: no evidence means a person looks ----

@pytest.mark.asyncio
async def test_a_file_no_signal_understands_goes_to_review(tmp_path):
    junk = tmp_path / "voice.mp3"
    junk.write_bytes(b"\x00\x01 not really audio " * 50)
    signals, scoring = await analyze_media(str(junk), "h")
    assert scoring.enforcement_action == "MANUAL_REVIEW"
    by_name = {s.plugin_name: s for s in signals}
    assert by_name["ContentSignal"].confidence == 0.0
    assert by_name["NetworkSignal"].confidence == 0.0 and by_name["IntegritySignal"].confidence == 0.0


# ---- trained model (ONNX) ----

def build_tiny_model(path):
    """x[1,3,8,8] -> mean per channel -> logits [10 * red, 0]: bright red looks 'real'."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 8, 8])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 2])
    w = numpy_helper.from_array(np.array([[10, 0], [0, 0], [0, 0]], dtype=np.float32), "w")
    graph = helper.make_graph(
        [helper.make_node("GlobalAveragePool", ["x"], ["p"]), helper.make_node("Flatten", ["p"], ["f"]),
         helper.make_node("MatMul", ["f", "w"], ["y"])],
        "tiny", [x], [y], [w],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, str(path))


@pytest.mark.asyncio
async def test_onnx_detector_scores_images_and_versions_itself(tmp_path):
    from app.signals.onnx_detector import OnnxImageDetector

    model = tmp_path / "tiny.onnx"
    build_tiny_model(model)
    (tmp_path / "tiny.json").write_text(json.dumps(
        {"version": "tiny-1", "input_size": [8, 8], "real_index": 0, "confidence": 0.7}))
    red, blue = tmp_path / "red.png", tmp_path / "blue.png"
    Image.new("RGB", (32, 32), (255, 0, 0)).save(red)
    Image.new("RGB", (32, 32), (0, 0, 255)).save(blue)

    det = OnnxImageDetector(str(model))
    r, b = await det.analyze(str(red), "h"), await det.analyze(str(blue), "h")
    assert r.score > 99 and b.score == pytest.approx(50.0, abs=0.5) and r.confidence == 0.7
    assert det.version.startswith("tiny-1@") and r.metadata["model_version"] == det.version

    bad = tmp_path / "notimage.bin"
    bad.write_bytes(b"nope")
    assert (await det.analyze(str(bad), "h")).confidence == 0.0
