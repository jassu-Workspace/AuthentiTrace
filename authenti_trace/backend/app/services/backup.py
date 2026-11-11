"""Backup and restore for the SQLite database and the ledger anchor file.

  python -m app.services.backup backup  --to backups/2026-01-15
  python -m app.services.backup restore --from backups/2026-01-15 --db restored.db --anchor restored_anchor.jsonl
  python -m app.services.backup verify  --db restored.db --anchor restored_anchor.jsonl

backup uses SQLite's online backup, so it is safe while the API is running. restore refuses a backup whose
files no longer match the checksums in manifest.json. verify runs the full ledger audit on a database file.
For Postgres use pg_dump / pg_restore (see docs/runbooks/restore.md) and copy the anchor file next to the dump.
"""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import database
from app.services import ledger_service


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sqlite_path(url: str) -> Path:
    prefix = "sqlite+aiosqlite:///"
    if not url.startswith(prefix):
        raise SystemExit("This tool only handles SQLite. For Postgres use pg_dump (docs/runbooks/restore.md).")
    return Path(url[len(prefix):])


def backup(db_path: Path, anchor_path: str, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "ledger.db"
    src, dst = sqlite3.connect(db_path), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    manifest = {"db_sha256": _sha256(target), "anchor_sha256": None}
    if anchor_path and os.path.exists(anchor_path):
        shutil.copyfile(anchor_path, dest / "ledger_anchor.jsonl")
        manifest["anchor_sha256"] = _sha256(dest / "ledger_anchor.jsonl")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def restore(src: Path, db_target: Path, anchor_target: Path) -> None:
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    if _sha256(src / "ledger.db") != manifest["db_sha256"]:
        raise SystemExit("Backup database does not match its checksum. Refusing to restore.")
    if manifest["anchor_sha256"] and _sha256(src / "ledger_anchor.jsonl") != manifest["anchor_sha256"]:
        raise SystemExit("Backup anchor file does not match its checksum. Refusing to restore.")
    shutil.copyfile(src / "ledger.db", db_target)
    if manifest["anchor_sha256"]:
        shutil.copyfile(src / "ledger_anchor.jsonl", anchor_target)


async def verify(db_path: Path, anchor_path: str) -> dict:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    previous = ledger_service.ANCHOR_PATH
    ledger_service.ANCHOR_PATH = anchor_path
    try:
        async with async_sessionmaker(bind=engine)() as db:
            return await ledger_service.audit_chain(db)
    finally:
        ledger_service.ANCHOR_PATH = previous
        await engine.dispose()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--to", type=Path, required=True)
    r = sub.add_parser("restore")
    r.add_argument("--from", dest="src", type=Path, required=True)
    r.add_argument("--db", type=Path, required=True)
    r.add_argument("--anchor", type=Path, required=True)
    v = sub.add_parser("verify")
    v.add_argument("--db", type=Path, required=True)
    v.add_argument("--anchor", default="")
    args = ap.parse_args(argv)

    if args.cmd == "backup":
        print(json.dumps(backup(_sqlite_path(database.SQLALCHEMY_DATABASE_URL), ledger_service.ANCHOR_PATH, args.to)))
    elif args.cmd == "restore":
        restore(args.src, args.db, args.anchor)
        print("restored; now run the verify command on the restored files")
    else:
        result = asyncio.run(verify(args.db, args.anchor))
        print(json.dumps(result))
        return 0 if result["ledger_intact"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
