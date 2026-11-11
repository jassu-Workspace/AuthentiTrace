"""Fit score calibration from a run_eval result and write backend/calibration.json.

Usage (from backend/), on the VALIDATION split only:
    CALIBRATION_PATH=none python -m eval.run_eval --manifest eval/data/manifest.csv --split val --out eval/results/val.json
    python -m eval.fit_calibration eval/results/val.json --version cal-2026-01
CALIBRATION_PATH=none makes that run use raw scores. Abstained rows (MANUAL_REVIEW) are skipped.
"""
import argparse
import json
import sys
from pathlib import Path

from app.services.calibration import CALIBRATION_PATH, fit_platt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", type=Path)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, default=Path(CALIBRATION_PATH))
    args = ap.parse_args(argv)

    report = json.loads(args.results.read_text(encoding="utf-8"))
    if report.get("split") == "test":
        print("Refusing to fit on the test split.", file=sys.stderr)
        return 2
    rows = [r for r in report["rows"] if r["action"] != "MANUAL_REVIEW"]
    try:
        a, b = fit_platt([r["score"] for r in rows], [int(r["label"] == "real") for r in rows])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.out.write_text(json.dumps({"type": "platt", "a": a, "b": b, "version": args.version, "n": len(rows)}, indent=2))
    print(f"wrote {args.out}: a={a:.4f} b={b:.4f} from {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
