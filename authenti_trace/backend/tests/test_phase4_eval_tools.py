import json

import numpy as np
import pytest
from PIL import Image

from eval import fit_calibration, fit_fusion, make_splits, run_attacks
from eval.attacks import ATTACKS, apply_attack
from test_eval_harness import read, write_dataset


@pytest.mark.parametrize("name", sorted(ATTACKS))
def test_every_attack_writes_a_readable_image(tmp_path, name):
    src = tmp_path / "src.png"
    arr = (np.random.default_rng(0).uniform(0, 255, (64, 64, 3))).astype("uint8")
    Image.fromarray(arr).save(src)
    out = apply_attack(name, src, tmp_path / f"{name}.png")
    with Image.open(out) as img:
        assert img.size[0] >= 8 and img.size[1] >= 8
    assert out.read_bytes() != src.read_bytes()


def test_run_attacks_reports_every_attack_and_flip_rate(tmp_path):
    manifest = write_dataset(tmp_path, n=12)
    make_splits.main([str(manifest), "--seed", "7"])
    split = next(s for s in ("train", "val", "test") if any(r["split"] == s for r in read(manifest)))
    out = tmp_path / "attacks.json"
    assert run_attacks.main(["--manifest", str(manifest), "--split", split, "--attacks", "jpeg_q50", "screenshot",
                             "--out", str(out)]) == 0
    report = json.loads(out.read_text())
    assert set(report["attacks"]) == {"jpeg_q50", "screenshot"}
    assert 0.0 <= report["attacks"]["screenshot"]["verdict_flip_rate"] <= 1.0
    assert "false_approval_rate" in report["clean"]


def test_run_attacks_rejects_bad_input(tmp_path):
    assert run_attacks.main(["--manifest", str(tmp_path / "x.csv"), "--split", "val"]) == 2
    manifest = write_dataset(tmp_path)
    assert run_attacks.main(["--manifest", str(manifest), "--split", "val", "--attacks", "nope"]) == 2


def result_rows(split="val"):
    rng = np.random.default_rng(3)
    rows = []
    for _ in range(300):
        real = int(rng.integers(0, 2))
        s = float(np.clip(rng.normal(75 if real else 35, 12), 0, 100))
        rows.append({"label": "real" if real else "fake", "score": s, "action": "APPROVE",
                     "signals": {"A": {"score": s, "confidence": 0.9}, "B": {"score": 50.0, "confidence": 0.9}}})
    return {"split": split, "rows": rows}


def test_fit_tools_write_files_and_refuse_the_test_split(tmp_path):
    val = tmp_path / "val.json"
    val.write_text(json.dumps(result_rows("val")))
    cal_out, fus_out = tmp_path / "cal.json", tmp_path / "fus.json"
    assert fit_calibration.main([str(val), "--version", "c1", "--out", str(cal_out)]) == 0
    assert fit_fusion.main([str(val), "--version", "f1", "--out", str(fus_out)]) == 0
    assert json.loads(cal_out.read_text())["version"] == "c1" and json.loads(cal_out.read_text())["a"] > 0
    weights = json.loads(fus_out.read_text())["weights"]
    assert weights["A"] > weights["B"]  # A carries the signal, B is constant noise

    test_split = tmp_path / "test.json"
    test_split.write_text(json.dumps(result_rows("test")))
    assert fit_calibration.main([str(test_split), "--version", "x", "--out", str(tmp_path / "n.json")]) == 2
    assert fit_fusion.main([str(test_split), "--version", "x", "--out", str(tmp_path / "n2.json")]) == 2
    assert not (tmp_path / "n.json").exists()


def test_fit_calibration_needs_both_classes(tmp_path):
    only_real = {"split": "val", "rows": [{"label": "real", "score": 80, "action": "APPROVE", "signals": {}}] * 5}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(only_real))
    assert fit_calibration.main([str(path), "--version", "x", "--out", str(tmp_path / "o.json")]) == 2
