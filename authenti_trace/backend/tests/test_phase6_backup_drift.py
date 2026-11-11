import asyncio
import json
import sqlite3
from datetime import timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import database
from app.models.ledger import Base, VerificationRecord, utcnow
from app.services import backup, drift_check, ledger_service
from app.services.ledger_service import commit_verification


@pytest.fixture
def live_db(tmp_path, monkeypatch):
    """A SQLite ledger with 3 rows and an anchor file, wired in as the app's database."""
    db_file = tmp_path / "live.db"
    url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    anchor = tmp_path / "anchor.jsonl"
    monkeypatch.setattr(ledger_service, "ANCHOR_PATH", str(anchor))
    monkeypatch.setattr(database, "SQLALCHEMY_DATABASE_URL", url)

    async def seed():
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(bind=engine)() as db:
            for i in range(3):
                await commit_verification(db, f"m{i}", f"h{i}", 80.0, "LOW_RISK", "APPROVE", {"i": i})
        await engine.dispose()

    asyncio.run(seed())
    return db_file, anchor, url


def test_backup_restore_roundtrip_passes_the_audit(live_db, tmp_path):
    db_file, anchor, _ = live_db
    dest = tmp_path / "bk"
    manifest = backup.backup(db_file, str(anchor), dest)
    assert manifest["db_sha256"] and manifest["anchor_sha256"]

    new_db, new_anchor = tmp_path / "restored.db", tmp_path / "restored_anchor.jsonl"
    backup.restore(dest, new_db, new_anchor)
    result = asyncio.run(backup.verify(new_db, str(new_anchor)))
    assert result["ledger_intact"] is True and result["chain_length"] == 3 and result["anchor_head_seq"] == 3


def test_restore_refuses_a_backup_that_was_changed(live_db, tmp_path):
    db_file, anchor, _ = live_db
    dest = tmp_path / "bk"
    backup.backup(db_file, str(anchor), dest)
    (dest / "ledger_anchor.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="anchor"):
        backup.restore(dest, tmp_path / "r.db", tmp_path / "r.jsonl")
    assert not (tmp_path / "r.db").exists()

    backup.backup(db_file, str(anchor), dest)  # fresh, valid backup
    with open(dest / "ledger.db", "ab") as f:
        f.write(b"tamper")
    with pytest.raises(SystemExit, match="database"):
        backup.restore(dest, tmp_path / "r.db", tmp_path / "r.jsonl")


def test_a_restored_database_with_an_edited_row_fails_verification(live_db, tmp_path):
    db_file, anchor, _ = live_db
    dest = tmp_path / "bk"
    backup.backup(db_file, str(anchor), dest)
    restored = tmp_path / "r.db"
    backup.restore(dest, restored, tmp_path / "r.jsonl")
    con = sqlite3.connect(restored)
    con.execute("UPDATE verification_ledger SET composite_score = 1.0 WHERE seq = 2")
    con.commit()
    con.close()
    assert asyncio.run(backup.verify(restored, str(tmp_path / "r.jsonl")))["ledger_intact"] is False
    assert backup.main(["verify", "--db", str(restored), "--anchor", str(tmp_path / "r.jsonl")]) == 1


def test_backup_cli_rejects_non_sqlite(monkeypatch):
    monkeypatch.setattr(database, "SQLALCHEMY_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    with pytest.raises(SystemExit, match="pg_dump"):
        backup.main(["backup", "--to", "x"])


def test_drift_check_exit_codes(live_db, monkeypatch, capsys):
    _, _, url = live_db
    engine = create_async_engine(url)
    factory = async_sessionmaker(bind=engine)
    monkeypatch.setattr(drift_check, "SessionLocal", factory)

    async def add_scores(old_scores, new_scores):
        async with factory() as db:
            for i, s in enumerate(old_scores):
                await commit_verification(db, f"o{i}", "h", s, "LOW_RISK", "APPROVE", {})
            for i, s in enumerate(new_scores):
                await commit_verification(db, f"n{i}", "h", s, "LOW_RISK", "APPROVE", {})
            await db.execute(update(VerificationRecord).where(VerificationRecord.media_reference_id.like("o%"))
                             .values(created_at=utcnow() - timedelta(days=10)))
            await db.execute(update(VerificationRecord).where(VerificationRecord.media_reference_id.like("m%"))
                             .values(created_at=utcnow() - timedelta(days=100)))
            await db.commit()

    asyncio.run(add_scores([float(x % 100) for x in range(60)], [float(x % 100) for x in range(60)]))
    assert asyncio.run(drift_check.main(7)) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "stable"

    asyncio.run(add_scores([], [95.0] * 80))  # recent scores pile up at the top: a large shift
    assert asyncio.run(drift_check.main(7)) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "alert"
    asyncio.run(engine.dispose())
