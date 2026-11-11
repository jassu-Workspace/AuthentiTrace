# Audit findings and where each is fixed

From the repo audit at the start of the plan.

| # | Finding | Severity | Fixed in |
|---|---|---|---|
| 1 | Uploaded media and DB committed to git; no `.gitignore` | Must | Phase 0 (0.2, 0.3, 0.4) |
| 2 | No limits; uploads never cleaned; metrics/audit load all rows | Must | Phase 0 (cleanup on failure), Phase 3 done (retention purge, grouped metrics, batched audit). Still open: login and rate limits (Phase 6.5) |
| 3 | Ledger lock works in one process only; ordering by `created_at` | Must | Phase 3 DONE (`seq`, unique head guards, retry) |
| 4 | Deleted tail rows and `created_at` edits not detected | Must | Phase 3 DONE (hash v2 with created_at, anchor file, truncation test) |
| 5 | Crashed signal scores 0 with confidence 1, caps score at 20 | Must | Phase 0 (0.10) |
| 6 | Empty registries and always-clean signals inflate trust | Must | Phase 4 code DONE (no evidence = zero weight; abstain path). Still needs your registry data and a trained model |
| 7 | Exception text returned to clients and stored in the ledger | Must | Phase 0 (0.9) |
| 8 | CPU-bound analysis blocks the event loop | Should | Phase 3 DONE (threads and timeout; background jobs) |
| 9 | Extension and type from client; orphan files on failure | Should | Phase 0 (0.11) |
| 10 | Integrity check re-hashes the file it just hashed; cannot fail | Should | Phase 0 (0.7) |
| 11 | No tests for scoring, upload limits, upload endpoint | Should | Phase 0 (0.6), Phase 3 exit criteria |
| 12 | Unpinned dependencies; dev packages missing | Should | Phase 0 (0.5) |
| 13 | Extra docs and unused imports | Nice | Phase 0 (0.8, 0.13) |
| 14 | Large uncommitted working tree; `HEAD` differs from running code | Nice | Phase 0 (0.1) |
