"""Assign train/val/test splits and lock the test set.

Usage (from backend/):
    python -m eval.make_splits eval/data/manifest.csv --seed 1337

Manifest columns: path,label,media_type,source,generator,transform[,sha256,split]
- path is relative to the manifest folder.
- Split is a stable hash of (seed, sha256), so re-running never moves a file.
- Files from the same `source` stay in one split (no near-duplicate leakage).
- The test set is locked in test_lock.json (hash of the sorted test sha256 values).
  Changing the test set afterwards fails loudly. Delete the lock only on purpose.
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

SPLIT_RATIOS = (("train", 0.70), ("val", 0.15), ("test", 0.15))
REQUIRED = {"path", "label", "media_type", "source", "generator", "transform"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_for(seed: int, group: str) -> str:
    """Stable split from a hash of (seed, group)."""
    bucket = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest(), 16) % 10_000 / 10_000
    edge = 0.0
    for name, ratio in SPLIT_RATIOS:
        edge += ratio
        if bucket < edge:
            return name
    return SPLIT_RATIOS[-1][0]


def test_set_digest(rows: list[dict]) -> str:
    shas = sorted(r["sha256"] for r in rows if r["split"] == "test")
    return hashlib.sha256("\n".join(shas).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args(argv)

    base = args.manifest.parent
    with args.manifest.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            print(f"manifest missing columns: {sorted(missing)}", file=sys.stderr)
            return 2
        rows = list(reader)

    for r in rows:
        if r["label"] not in {"real", "fake"}:
            print(f"bad label {r['label']!r} for {r['path']}", file=sys.stderr)
            return 2
        r["sha256"] = file_sha256(base / r["path"])
        r["split"] = split_for(args.seed, r["source"] or r["sha256"])

    lock_path = base / "test_lock.json"
    digest = test_set_digest(rows)
    if lock_path.exists():
        locked = json.loads(lock_path.read_text(encoding="utf-8"))
        if locked["digest"] != digest:
            print("TEST SET CHANGED since it was locked. Refusing to write. Delete test_lock.json only on purpose.",
                  file=sys.stderr)
            return 3
    else:
        lock_path.write_text(json.dumps({"seed": args.seed, "digest": digest}, indent=2), encoding="utf-8")

    fields = list(rows[0].keys()) if rows else sorted(REQUIRED | {"sha256", "split"})
    with args.manifest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    counts = {}
    for r in rows:
        counts[r["split"]] = counts.get(r["split"], 0) + 1
    print(f"splits: {counts}; test digest {digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
