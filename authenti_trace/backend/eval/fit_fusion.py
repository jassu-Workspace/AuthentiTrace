"""Learn per-signal fusion weights from a run_eval result and write backend/fusion.json.

Usage (from backend/), on the VALIDATION split only:
    python -m eval.run_eval --manifest eval/data/manifest.csv --split val --out eval/results/val.json
    python -m eval.fit_fusion eval/results/val.json --version fus-2026-01
"""
import argparse
import json
import sys
from pathlib import Path

from app.services.calibration import FUSION_PATH, fit_fusion_weights


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", type=Path)
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, default=Path(FUSION_PATH))
    args = ap.parse_args(argv)

    report = json.loads(args.results.read_text(encoding="utf-8"))
    if report.get("split") == "test":
        print("Refusing to fit on the test split.", file=sys.stderr)
        return 2
    rows = report["rows"]
    try:
        weights = fit_fusion_weights([r["signals"] for r in rows], [int(r["label"] == "real") for r in rows])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.out.write_text(json.dumps({"weights": weights, "version": args.version, "n": len(rows)}, indent=2))
    print(f"wrote {args.out}: {weights}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
