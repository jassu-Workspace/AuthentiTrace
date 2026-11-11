"""Run the full pipeline over one split and report metrics. No database writes.

Usage (from backend/):
    python -m eval.run_eval --manifest eval/data/manifest.csv --split val
    python -m eval.run_eval --manifest eval/data/manifest.csv --split val --thresholds eval/thresholds.json
    python -m eval.run_eval --manifest eval/data/manifest.csv --split test --out eval/results/test.json

The locked test split is for final reporting only. Never tune on it.
Exit code: 0 ok, 1 thresholds failed, 2 bad input.
"""
import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path

from eval.make_splits import file_sha256
from eval.metrics import check_thresholds, summarize
from app.services.verification_service import analyze_media


async def evaluate(manifest: Path, split: str) -> list[dict]:
    base = manifest.parent
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("split") == split]

    results = []
    for r in rows:
        path = base / r["path"]
        sha = r.get("sha256") or file_sha256(path)
        start = time.perf_counter()
        signals, scoring = await analyze_media(str(path), sha)
        results.append({
            "path": r["path"],
            "label": r["label"],
            "media_type": r.get("media_type", ""),
            "generator": r.get("generator", ""),
            "transform": r.get("transform", ""),
            "score": scoring.trust_score,
            "action": scoring.enforcement_action,
            "latency_s": time.perf_counter() - start,
            "signals": {s.plugin_name: {"score": s.score, "confidence": s.confidence} for s in signals},
        })
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--split", choices=["train", "val", "test"], required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--thresholds", type=Path, help="JSON of upper bounds, e.g. {\"false_approval_rate\": 0.1}")
    args = ap.parse_args(argv)

    if not args.manifest.exists():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    results = asyncio.run(evaluate(args.manifest, args.split))
    if not results:
        print(f"no rows in split {args.split!r}. Run eval.make_splits first.", file=sys.stderr)
        return 2

    summary = summarize(results)
    report = {"split": args.split, "summary": summary, "rows": results}
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    if args.thresholds:
        failures = check_thresholds(summary, json.loads(args.thresholds.read_text(encoding="utf-8")))
        if failures:
            print("THRESHOLDS FAILED:\n  " + "\n  ".join(failures), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
