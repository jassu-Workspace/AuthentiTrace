"""Tests the evaluation tooling itself (math and plumbing). Synthetic files here are for the tooling only,
never for measuring detection quality."""
import csv
import json

import pytest
from PIL import Image

from eval import make_splits, run_eval
from eval.metrics import (
    calibration_bins, check_thresholds, false_alarm_rate, false_approval_rate,
    latency_percentiles, summarize, unsure_rate,
)


def row(label, action, score=50.0, **extra):
    return {"label": label, "action": action, "score": score, "latency_s": 0.1, **extra}


def test_error_rate_definitions():
    rows = [
        row("fake", "APPROVE"), row("fake", "FLAG"), row("fake", "MANUAL_REVIEW"), row("fake", "RESTRICT"),
        row("real", "APPROVE"), row("real", "FLAG"), row("real", "RESTRICT"), row("real", "MANUAL_REVIEW"),
    ]
    assert false_approval_rate(rows) == 0.25       # 1 of 4 fakes approved
    assert false_alarm_rate(rows) == 0.5           # FLAG + RESTRICT of 4 reals
    assert unsure_rate(rows) == 0.25               # 2 of 8


def test_rates_are_none_without_data():
    assert false_approval_rate([row("real", "APPROVE")]) is None
    assert false_alarm_rate([row("fake", "APPROVE")]) is None


def test_calibration_gap_detects_overconfidence():
    # Scored ~95 but only half are real: expected 0.95, observed 0.5
    rows = [row("real", "APPROVE", 95), row("fake", "APPROVE", 95)]
    (b,) = calibration_bins(rows)
    assert b["bin"] == "90-100" and b["observed_real"] == 0.5 and b["gap"] == pytest.approx(0.45)


def test_latency_percentiles():
    rows = [{"latency_s": v} for v in [1, 2, 3, 4, 100]]
    assert latency_percentiles(rows)["max"] == 100
    assert latency_percentiles([]) == {"p50": None, "p95": None, "max": None}


def test_threshold_check():
    s = {"false_approval_rate": 0.2, "unsure_rate": None}
    assert check_thresholds(s, {"false_approval_rate": 0.3}) == []
    assert len(check_thresholds(s, {"false_approval_rate": 0.1})) == 1
    assert "no data" in check_thresholds(s, {"unsure_rate": 0.5})[0]


# ---- splits ----

def write_dataset(tmp_path, n=12):
    rows = []
    for i in range(n):
        name = f"img{i}.png"
        Image.new("RGB", (48, 48), (i * 10 % 255, 50, 90)).save(tmp_path / name)
        rows.append({"path": name, "label": "real" if i % 2 else "fake", "media_type": "image",
                     "source": f"src{i // 2}", "generator": "none" if i % 2 else "gen", "transform": "none"})
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return manifest


def read(manifest):
    with manifest.open(newline="") as f:
        return list(csv.DictReader(f))


def test_splits_are_stable_and_group_by_source(tmp_path):
    manifest = write_dataset(tmp_path)
    assert make_splits.main([str(manifest), "--seed", "7"]) == 0
    first = {r["path"]: r["split"] for r in read(manifest)}
    assert make_splits.main([str(manifest), "--seed", "7"]) == 0
    assert {r["path"]: r["split"] for r in read(manifest)} == first
    by_source = {}
    for r in read(manifest):
        by_source.setdefault(r["source"], set()).add(r["split"])
    assert all(len(v) == 1 for v in by_source.values())


def test_locked_test_set_refuses_change(tmp_path):
    manifest = write_dataset(tmp_path)
    assert make_splits.main([str(manifest), "--seed", "7"]) == 0
    # Change the seed: the test set would change, so it must be refused
    assert make_splits.main([str(manifest), "--seed", "8"]) == 3
    assert json.loads((tmp_path / "test_lock.json").read_text())["seed"] == 7


def test_bad_label_rejected(tmp_path):
    manifest = write_dataset(tmp_path)
    text = manifest.read_text().replace(",fake,", ",bogus,", 1)
    manifest.write_text(text)
    assert make_splits.main([str(manifest), "--seed", "1"]) == 2


# ---- run_eval plumbing ----

def test_run_eval_reports_and_gates(tmp_path):
    manifest = write_dataset(tmp_path)
    make_splits.main([str(manifest), "--seed", "7"])
    split = next(s for s in ("train", "val", "test") if any(r["split"] == s for r in read(manifest)))
    out = tmp_path / "res" / "r.json"

    assert run_eval.main(["--manifest", str(manifest), "--split", split, "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    assert report["summary"]["n"] == len([r for r in read(manifest) if r["split"] == split])
    assert {"false_approval_rate", "calibration", "by_generator", "latency_s"} <= set(report["summary"])

    impossible = tmp_path / "t.json"
    impossible.write_text(json.dumps({"latency_s_p95_never": 0}))  # unknown metric has no data
    assert run_eval.main(["--manifest", str(manifest), "--split", split, "--thresholds", str(impossible)]) == 1


def test_run_eval_missing_manifest_and_empty_split(tmp_path):
    assert run_eval.main(["--manifest", str(tmp_path / "nope.csv"), "--split", "val"]) == 2
    manifest = write_dataset(tmp_path)  # no splits assigned yet
    assert run_eval.main(["--manifest", str(manifest), "--split", "val"]) == 2


def test_summarize_shape():
    s = summarize([row("real", "APPROVE", 90, media_type="image", generator="none")])
    assert s["by_media_type"]["image"]["n"] == 1
