# Plan status

Update after every finished task. Add proof (test output, build output, or diff) next to each completed item.

Current phase: Phase 0 done on branch `phase-0-stabilize` (not pushed). Waiting for user decisions before Phases 1 and 2.

| Phase | State | Branch | Proof / notes |
|---|---|---|---|
| 0 Stabilize | done | phase-0-stabilize | 24 backend tests pass; ruff F clean; `npm run lint` 0 errors (1 `<img>` warning); `npm run build` ok; upload smoke test ok |
| 1 Problem | drafted, awaiting approval | phase-1-spec | `docs/spec/problem-spec.md`. Niche is a provisional default. 1.1, 1.4, 1.5 still open |
| 2 Evaluation | tooling done, baseline blocked | phase-2-eval | `backend/eval/` (metrics, make_splits, run_eval) + 11 tests. Baseline needs user data: see `docs/plan/baseline.md` |
| 3 Architecture | mostly done (see deviations) | phase-3-architecture | 54 tests pass. 50 simultaneous uploads: all 202, all done (p95 5.4 s), `/metrics` stayed up, audit intact. Open: Celery/Redis, Postgres, S3 adapter |
| 4 Detection | code done, model and numbers need you | phase-4-detection | abstain path, real C2PA, ONNX plug-in, fusion/calibration/attack tools, 92 tests. Real model, baseline and tuned thresholds need your data and GPU |
| 5 Product | done (no formal accessibility audit) | phase-5-product | job-status upload, plain-language report, UNSURE state, review queue, verify page, quality dashboard; 103 backend tests; lint, tsc and build clean; walked through in a browser |
| 6 Operations | done in code; deploy and real-data items need you | phase-6-ops | 131 backend tests; auth, rate limits, file checks, metrics, backup/restore, drift check, Docker, CI, runbooks. See docs/HANDOFF.md |

## Scores

| Area | Start | Now | Target |
|---|---|---|---|
| Problem | 82 | 82 | 95+ |
| Architecture | 60 | ~80 (self-estimate) | 90+ |
| Solution | 35 | 35 | 85+ |

## Open questions for the user
1. Niche and buyer?
2. Source of real and fake media?
3. GPU option?
4. Acceptable false-approval and false-alarm rates?

## Log
- Plan created. No code changed.
- Phase 0 executed. Closed audit findings 1, 5, 7, 9, 10, 12, 13, 14. Also closed the cleanup part of 2.
- 0.3: tracking stopped for media and `.db` files. Git history still contains old media; purging it needs the user's OK (filter-repo, force-push).
- 0.12: production without `NEXT_PUBLIC_API_URL` uses relative paths; documented in `frontend/VERCEL_DEPLOYMENT.md`. No code change.
- Added: scoring returns `UNKNOWN` / `MANUAL_REVIEW` when every signal has zero confidence.
- Not run: `securitymaxxing:diff`, a fresh-clone install test, Python 3.12 run (local Python is 3.14).
- Phase 1: spec drafted with a provisional niche (claim/listing photos). No numbers invented. Competitor research not done.
- Phase 2: harness built (`backend/eval/`). `analyze_media()` split from the ledger path; signals run in threads with a timeout. No baseline: no labeled data.
- Phase 3 done on SQLite with an in-process job runner. Deviations: no Celery/Redis (YAGNI at this load; `enqueue()` is the swap point), no Postgres (none available; Docker daemon was off), no S3 adapter. These keep Architecture below 90.
- Phase 3 load test (local, SQLite): 50 simultaneous 640x480 JPEG uploads, 202 for all, p50 4.6 s and p95 5.4 s to done, dashboard probe p95 0.64 s, audit intact. Not a production capacity number.
- Found by that test: job id read after commit (fixed, regression test added); recovered jobs with missing media wrote ledger rows (now fail with MEDIA_MISSING).
- Anchor file is a shortcut: anyone who can edit both the DB and the file can rewrite both. Copy it to storage the DB admin cannot write.
- Not run: `securitymaxxing:diff`/`audit`/`ship-check` (required at Phase 3 end by CLAUDE.md), Python 3.12, frontend build after Phase 3 (no frontend change).
- Phase 3 completed: Celery path (tested with a real Redis 3.0.504 and two worker processes: 50 jobs, audit intact), atomic job claiming, stale-job recovery, S3/local object stores (moto-tested), Postgres URL supported (untested, no Postgres here). 62 tests.
- Phase 4: forged C2PA byte markers no longer score 98 (found while wiring the real library). Empty registries and unreadable files now carry zero weight. New abstain rules use uncalibrated limits (`SCORING_MIN_EVIDENCE`, `SCORING_MAX_DISAGREEMENT`). Stripped-metadata fakes can still be approved: only a trained detector fixes that.
- Phase 5: new endpoints `/reviews`, `/reports/{id}/proof`, `/reports/by-hash/{hash}`, `/dashboard/quality`. Review decisions are new ledger rows. Telemetry keys that start with `_` are not signals.
- Phase 6: found by testing the real proxy: Next.js trailing-slash redirect broke streamed uploads (fixed with `skipTrailingSlashRedirect` and exact path forwarding). Compose and Dockerfiles were not run (no Docker daemon). See `docs/HANDOFF.md` for everything that needs you.
