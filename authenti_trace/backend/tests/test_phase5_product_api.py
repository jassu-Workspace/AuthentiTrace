import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints import dashboard, reports, reviews
from app.database.database import get_db
from app.models.ledger import Base
from app.services.drift import drift_status, histogram, psi
from app.services.ledger_service import audit_chain, commit_verification, prove


@pytest_asyncio.fixture
async def factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 't.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(bind=engine)
    await engine.dispose()


@pytest.fixture
def client(factory):
    app = FastAPI()
    app.include_router(reviews.router, prefix="/reviews")
    app.include_router(reports.router, prefix="/reports")
    app.include_router(dashboard.router, prefix="/dashboard")

    async def override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    return TestClient(app)


async def seed(factory):
    """Rows: 1 approved, 2 needs review (reason stored), 3 flagged, 4 restricted."""
    specs = [
        ("m1", "a" * 64, 90.0, "LOW_RISK", "APPROVE", {}),
        ("m2", "b" * 64, 55.0, "UNKNOWN", "MANUAL_REVIEW", {"_decision": {"reason": "Not enough evidence to decide."}}),
        ("m3", "c" * 64, 60.0, "MEDIUM_RISK", "FLAG", {}),
        ("m4", "d" * 64, 10.0, "HIGH_RISK", "RESTRICT", {}),
    ]
    ids = []
    async with factory() as db:
        for spec in specs:
            ids.append((await commit_verification(db, *spec)).id)  # read the id before the next commit expires it
    return tuple(ids)


# ---- review queue ----

@pytest.mark.asyncio
async def test_pending_lists_only_verdicts_that_need_a_person(factory, client):
    a, b, c, d = await seed(factory)
    pending = client.get("/reviews/pending").json()
    assert {p["id"] for p in pending} == {b, c}
    assert next(p for p in pending if p["id"] == b)["reason"] == "Not enough evidence to decide."


@pytest.mark.asyncio
async def test_a_decision_is_a_new_row_that_clears_the_item_and_keeps_the_chain_intact(factory, client):
    a, b, c, d = await seed(factory)
    r = client.post(f"/reviews/{b}", json={"decision": "reject", "note": "Looks edited", "reviewer": "sam"})
    assert r.status_code == 201
    body = r.json()
    assert body["enforcement_action"] == "HUMAN_REJECT" and body["risk_category"] == "REVIEWED"
    assert body["seq"] == 5 and body["signal_telemetry"]["_review"] == {
        "of": b, "decision": "reject", "note": "Looks edited", "reviewer": "sam"}

    assert {p["id"] for p in client.get("/reviews/pending").json()} == {c}
    async with factory() as db:
        assert (await audit_chain(db))["ledger_intact"] is True
        # The reviewed row itself is untouched
        row = (await db.execute(text("SELECT enforcement_action FROM verification_ledger WHERE id = :i"), {"i": b})).scalar()
        assert row == "MANUAL_REVIEW"


@pytest.mark.asyncio
async def test_review_rules(factory, client):
    a, b, c, d = await seed(factory)
    assert client.post(f"/reviews/{b}", json={"decision": "approve"}).status_code == 201
    assert client.post(f"/reviews/{b}", json={"decision": "approve"}).status_code == 409   # already reviewed
    assert client.post(f"/reviews/{a}", json={"decision": "approve"}).status_code == 422   # did not need review
    assert client.post("/reviews/nope", json={"decision": "approve"}).status_code == 404
    assert client.post(f"/reviews/{c}", json={"decision": "maybe"}).status_code == 422     # bad decision
    assert client.post(f"/reviews/{c}", json={"decision": "approve", "note": "x" * 501}).status_code == 422


@pytest.mark.asyncio
async def test_review_rows_are_not_counted_as_verifications_or_reviewable(factory, client):
    a, b, c, d = await seed(factory)
    client.post(f"/reviews/{b}", json={"decision": "approve"})
    m = client.get("/dashboard/metrics").json()
    assert m["total_verifications"] == 4 and m["risk_distribution"]["UNKNOWN"] == 1
    assert client.get("/dashboard/quality").json()["review_backlog"] == 1  # only the flagged row is left


# ---- proof and lookup by hash ----

@pytest.mark.asyncio
async def test_proof_for_an_intact_row(factory, client):
    a, *_ = await seed(factory)
    proof = client.get(f"/reports/{a}/proof").json()
    assert proof["verified"] is True and proof["hash_valid"] and proof["links_to_previous"]
    assert proof["seq"] == 1 and proof["anchored"] == "yes" and proof["chain_head_seq"] == 4


@pytest.mark.asyncio
async def test_proof_fails_for_a_tampered_row(factory, client):
    a, b, *_ = await seed(factory)
    async with factory() as db:
        await db.execute(text("UPDATE verification_ledger SET composite_score = 1.0 WHERE id = :i"), {"i": b})
        await db.commit()
    proof = client.get(f"/reports/{b}/proof").json()
    assert proof["hash_valid"] is False and proof["verified"] is False
    assert client.get(f"/reports/{a}/proof").json()["verified"] is True  # neighbours are unaffected


@pytest.mark.asyncio
async def test_proof_reports_a_broken_link_and_review_target(factory, client):
    a, b, *_ = await seed(factory)
    async with factory() as db:
        await db.execute(text("DELETE FROM verification_ledger WHERE id = :i"), {"i": a})
        await db.commit()
        record_b = (await db.execute(text("SELECT id FROM verification_ledger WHERE id = :i"), {"i": b})).scalar()
    assert record_b == b
    proof = client.get(f"/reports/{b}/proof").json()
    assert proof["links_to_previous"] is False and proof["verified"] is False
    client.post(f"/reviews/{b}", json={"decision": "approve"})  # the decision row points at b
    async with factory() as db:
        decision_id = (await db.execute(text(
            "SELECT id FROM verification_ledger WHERE risk_category = 'REVIEWED'"))).scalar()
    assert client.get(f"/reports/{decision_id}/proof").json()["review_of"] == b


@pytest.mark.asyncio
async def test_lookup_by_file_hash(factory, client):
    await seed(factory)
    rows = client.get("/reports/by-hash/" + "b" * 64).json()
    assert len(rows) == 1 and rows[0]["media_reference_id"] == "m2"
    assert client.get("/reports/by-hash/" + "e" * 64).status_code == 404
    assert client.get("/reports/by-hash/short").status_code == 422
    assert client.get("/reports/by-hash/" + "z" * 64).status_code == 422


@pytest.mark.asyncio
async def test_prove_without_an_anchor_file(factory, isolated_anchor):
    async with factory() as db:
        r = await commit_verification(db, "m", "h", 80.0, "LOW_RISK", "APPROVE", {})
        isolated_anchor.unlink()
        assert (await prove(db, r))["anchored"] == "no_anchor_file"


# ---- quality: drift, histogram, latest evaluation ----

def test_histogram_and_psi():
    assert histogram([5, 15, 95, 100, 100]) == [1, 1, 0, 0, 0, 0, 0, 0, 0, 3]
    same = [float(x) for x in range(0, 100, 2)] * 2
    assert psi(same, same) == 0.0
    shifted = [float(x) for x in range(60, 100)] * 2
    assert psi(same, shifted) > 0.25 and drift_status(psi(same, shifted)) == "alert"
    assert psi([1.0] * 5, [2.0] * 5) is None and drift_status(None) == "insufficient_data"
    assert drift_status(0.12) == "watch" and drift_status(0.01) == "stable"


@pytest.mark.asyncio
async def test_quality_reads_the_latest_eval_file(factory, client, tmp_path, monkeypatch):
    await seed(factory)
    assert client.get("/dashboard/quality").json()["latest_eval"] is None
    f = tmp_path / "latest.json"
    f.write_text(json.dumps({"split": "val", "summary": {"n": 10, "false_approval_rate": 0.1, "calibration": []}}))
    monkeypatch.setattr(dashboard, "EVAL_RESULTS_PATH", f)
    q = client.get("/dashboard/quality").json()
    assert q["latest_eval"]["false_approval_rate"] == 0.1 and "calibration" not in q["latest_eval"]
    assert q["drift"]["status"] == "insufficient_data" and q["recent_count"] == 4
    f.write_text("not json")
    assert client.get("/dashboard/quality").json()["latest_eval"] is None
