"""Measure how much each attack changes the system's verdicts. No database writes.

Usage (from backend/):
    python -m eval.run_attacks --manifest eval/data/manifest.csv --split val --out eval/results/attacks-val.json

For every image in the split it runs the clean file and each attack, then reports per attack:
false_approval_rate, false_alarm_rate, unsure_rate and verdict_flip_rate (share of files whose action
changed versus the clean file). Large flips mean the detector relies on fragile traces.
"""
import argparse
import asyncio
import csv
import json
import sys
import tempfile
from pathlib import Path

from eval.attacks import ATTACKS, apply_attack
from eval.make_splits import file_sha256
from eval.metrics import summarize
from app.services.verification_service import analyze_media


def _row(label: str, scoring) -> dict:
    return {"label": label, "action": scoring.enforcement_action, "score": scoring.trust_score,
            "latency_s": 0.0, "media_type": "image", "generator": ""}


async def run(manifest: Path, split: str, attacks: list[str]) -> dict:
    base = manifest.parent
    with manifest.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("split") == split and r.get("media_type", "image") == "image"]

    clean, attacked = [], {a: [] for a in attacks}
    with tempfile.TemporaryDirectory() as tmp:
        for r in rows:
            src = base / r["path"]
            _, scoring = await analyze_media(str(src), r.get("sha256") or file_sha256(src))
            clean.append(_row(r["label"], scoring))
            for name in attacks:
                out = apply_attack(name, src, Path(tmp) / f"{name}.png")
                _, s = await analyze_media(str(out), file_sha256(out))
                attacked[name].append(_row(r["label"], s))

    report = {"n": len(rows), "clean": _short(summarize(clean)), "attacks": {}}
    for name, results in attacked.items():
        flips = sum(a["action"] != c["action"] for a, c in zip(results, clean))
        short = _short(summarize(results))
        short["verdict_flip_rate"] = round(flips / len(results), 4) if results else None
        report["attacks"][name] = short
    return report


def _short(s: dict) -> dict:
    return {k: s[k] for k in ("false_approval_rate", "false_alarm_rate", "unsure_rate")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--split", choices=["train", "val", "test"], required=True)
    ap.add_argument("--attacks", nargs="*", default=list(ATTACKS))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    unknown = set(args.attacks) - set(ATTACKS)
    if unknown or not args.manifest.exists():
        print(f"bad input (unknown attacks: {sorted(unknown)}, manifest exists: {args.manifest.exists()})", file=sys.stderr)
        return 2
    report = asyncio.run(run(args.manifest, args.split, args.attacks))
    if not report["n"]:
        print("no image rows in that split", file=sys.stderr)
        return 2
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
