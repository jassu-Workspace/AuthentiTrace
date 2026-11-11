# CLAUDE.md — backend

Read the root `CLAUDE.md` first. This file covers `backend/` only.

## Layout
- `app/main.py` — app, CORS, lifespan (creates tables), routers under `/api/v1`.
- `app/api/v1/endpoints/` — `upload.py` (POST /upload/), `reports.py` (GET /reports/{id}), `dashboard.py` (/metrics, /audit).
- `app/services/` — `media_service.py` (save + hash), `verification_service.py` (pipeline), `scoring_engine.py`, `ledger_service.py`.
- `app/signals/` — `base.py` (ISignalPlugin), `heuristic_signals.py` (Content, Reality, Behavioral, Network), `integrity.py`.
- `app/models/ledger.py`, `app/schemas/verification.py`, `app/utils/security.py` (`calculate_ledger_hash`).
- `tests/` — `test_ledger.py`, `test_forensic_signals.py`.

## Data flow
upload -> `save_upload_and_hash` -> `process_verification` -> signals (gather) -> `calculate_trust_score` -> `commit_verification` (hash chain) -> `ReportResponse`.

## Rules for this folder
- Keep `ISignalPlugin` as the only signal interface. New signals implement it.
- CPU work in a signal runs in `asyncio.to_thread` (Phase 3). Do not add new blocking code in `async def`.
- Ledger writes go through `commit_verification` only. No other code writes `VerificationRecord`.
- Hash payload fields: media_id, file_hash, score (2 decimals), risk, action, telemetry. Phase 3 adds `created_at` and a version. Update `calculate_ledger_hash` callers in `ledger_service.py` and `dashboard.py` together. They must stay identical.
- Error messages to clients are fixed strings. Log details server-side.
- Stored file extension comes from a fixed MIME map, never from the client filename.
- Use an absolute path for the database. Never rely on the working directory.

## Tests
- Run: `python -m pytest -q` from `backend/`.
- Async tests use `pytest-asyncio`. Dev packages belong in `requirements-dev.txt` (Phase 0).
- Required coverage before Phase 3 exit: scoring rules, upload limits (413, 415), ledger fork under concurrent writers, `/audit` tamper detection.

## Phase map for this folder
- Phase 0: gitignore, pins, dead code, error text.
- Phase 3: seq column, single writer, anchor, jobs, workers, Postgres, versioning.
- Phase 4: new detectors behind `ISignalPlugin`, fusion, abstain.
