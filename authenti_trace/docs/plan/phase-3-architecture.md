# Phase 3 — Architecture upgrade (weeks 3-7)

Goal: Architecture score 60 → 90. Owner: Claude. Branch: `phase-3-architecture`. Starts after Phase 0 exit; Phase 2 can run in parallel.

## Tasks
### Ledger
- [ ] 3.1 Add `seq` (autoincrement integer, unique) to `VerificationRecord`. Order and chain by `seq`, not `created_at`.
- [ ] 3.2 Add `hash_version` and include `created_at` in the hashed payload. Keep a verifier path for old rows (version 1).
- [ ] 3.3 Single writer: Postgres `SELECT ... FOR UPDATE` on the head row, or one dedicated ledger-writer worker. Remove reliance on `asyncio.Lock`.
- [ ] 3.4 Head-hash anchor: write the latest `seq` and hash to a signed file or external log on a schedule and on each commit. `/audit` compares the DB head to the anchor and reports truncation.
- [ ] 3.5 Test: two concurrent writers produce no fork, and `/audit` stays clean. Test: deleting the last row is detected.

### Jobs and workers
- [ ] 3.6 Add Celery and Redis. `POST /upload/` saves the file, creates a job, returns `{job_id}` with 202.
- [ ] 3.7 `GET /jobs/{job_id}` returns status (`queued`, `running`, `done`, `failed`) and the report ID when done.
- [ ] 3.8 Each signal runs with a time limit. CPU work uses worker processes or `asyncio.to_thread`. A timeout or crash gives `confidence=0`.
- [ ] 3.9 Retries with limits and a dead-letter state. A failed job never writes a ledger row with fake scores.

### Storage and data
- [ ] 3.10 Move SQLite to Postgres. Add Alembic migrations. Remove `create_all` from lifespan.
- [ ] 3.11 Object storage interface (local disk adapter and S3 adapter). Retention rule: delete media after N days, keep the hash and report.
- [ ] 3.12 `/dashboard/metrics` as one grouped query. `/dashboard/audit` paginated or streamed.

### Versioning
- [ ] 3.13 Store `model_version`, `thresholds_version` and `pipeline_version` in each ledger row (inside the hashed payload).
- [ ] 3.14 `scripts/rescore.py`: re-score old media under a new version as new rows. Never edit old rows.

## Exit criteria
- 50 simultaneous uploads: API stays responsive, no 5xx, p95 recorded.
- Two worker processes: `/audit` clean, no chain fork.
- Deleted tail rows are detected.
- Tests cover scoring, upload limits, job lifecycle, ledger fork and truncation.
- Audit findings 2 (storage and query parts), 3, 4, 8 closed.
