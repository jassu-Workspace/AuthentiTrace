# CLAUDE.md — AuthentiTrace

Project rules and full project brief for Claude Code. Global rules in `~/.claude/CLAUDE.md` still apply. This file adds project facts, goals and targets. Read all of it at the start of every session.

---

## 0. Mandatory skills (every session, every task)

These skills are always allowed and always on. Do not ask permission to use them.

| Skill | Setting | What it does here |
|---|---|---|
| `ponytail:ponytail` | **ultra** | Smallest change that fully solves the task. Question requests the need does not justify. End every reply with what was skipped or not checked, and any risk. |
| `caveman:caveman` | **ultra** | Short, blunt replies. Applies to chat replies only. Code, docs and plan files stay in clear, complete plain English. |
| `superpowers:*` | always | Start with `superpowers:using-superpowers`. Use `brainstorming` before new features, `systematic-debugging` for bugs, `test-driven-development` for features and fixes, `writing-plans` and `executing-plans` for multi-step work, `verification-before-completion` before any success claim, `requesting-code-review` before finishing a phase. |
| `securitymaxxing:*` | always | Use `secure-coding` while writing routes, uploads, file paths, queries or subprocess code. Use `llm-app-security` for any model or agent feature. Run `securitymaxxing:diff` on every branch before it is called done. Run `securitymaxxing:audit` and `securitymaxxing:ship-check` at the end of Phases 3, 4 and 6. |

Order of use: process skills first (superpowers), then implementation skills (ponytail, security), then reply style (caveman).
If two skills conflict, safety and correctness win over brevity.

---

## 1. What AuthentiTrace is

AuthentiTrace is a media trust system. A user uploads an image, a video or an audio file. The system answers: **how likely is this media real, and can we prove what we said later?**

It does two jobs:
1. **Judge.** Independent signal plugins inspect the file. A scoring engine combines their results into a trust score, a risk category (`LOW_RISK`, `MEDIUM_RISK`, `HIGH_RISK`) and an action (`APPROVE`, `FLAG`, `RESTRICT`).
2. **Prove.** Every result is written to a hash-chained ledger. Each row's hash covers the row before it. If anyone edits or removes a row, an audit detects it.

The product value is the combination: a verdict plus a tamper-evident record of the verdict.

---

## 2. Where the project is today

### What exists (after phases 0-6; see docs/plan/STATUS.md and docs/HANDOFF.md)
- **Backend:** FastAPI, SQLAlchemy async with Alembic migrations, SQLite by default or Postgres (`DATABASE_URL`, untested on real Postgres), Celery + Redis workers when `CELERY_BROKER_URL` is set (otherwise an in-process runner), local or S3 media store.
- **Endpoints:** `/api/v1/jobs` (202 + polling), `/upload` (older blocking call), `/reports/{id}`, `/reports/{id}/proof`, `/reports/by-hash/{hash}`, `/reviews`, `/dashboard/{metrics,audit,quality}`, `/ops/metrics`, public `/health`. API keys (`API_KEYS`) and rate limits on everything except `/health`.
- **Signals:** Content, Reality (real C2PA check), Behavioral, Network, Integrity, plus an optional ONNX detector (`IMAGE_MODEL_PATH`). A signal with no evidence has confidence 0. The scoring engine abstains (MANUAL_REVIEW) on too little evidence or strong disagreement. Limits are uncalibrated placeholders.
- **Ledger:** `seq`, versioned hash (v2), unique seq/previous_hash fork guard, anchor file (deleted-tail detection), review decisions as new rows, backup/restore tool.
- **Frontend:** Next.js 16 with job-status upload, plain-language report, review queue, verify page, quality dashboard, and an `/api` server proxy that adds the key. No user login yet.
- **Measurement:** `backend/eval` (metrics, locked splits, attacks, calibration and fusion fitting). No labeled data yet, so no baseline.
- **Ops:** Dockerfiles, docker-compose (never run), CI workflow, runbooks in `docs/runbooks`.
- **Tests:** 135 backend tests; frontend lint, tsc and build clean.

### What is still weak
- Detection is rule-based unless a model is configured; a fake with stripped metadata can still be approved. No labeled data, no measured error rates, scores uncalibrated.
- Registries are empty. Video and audio have no detector (they go to human review).
- The web app has no user login (see docs/plan/security-review.md, finding 1).

### Scores at the start of the plan (out of 100, excluding Docker, auth and rate limiting)
| Area | Start |
|---|---|
| Problem | 82 |
| Architecture | 60 |
| Solution | 35 |

---

## 3. Goals and targets (the finish line)

### Main goal
Turn the prototype into a production-grade media-authenticity system whose scores are **measured, calibrated and provable**, not guessed.

### Score targets
| Area | Start | Target | What reaching it means |
|---|---|---|---|
| Problem | 82 | **95+** | One named niche, one named buyer, written success metrics, a clear edge over competitors. |
| Architecture | 60 | **90+** | Background jobs, safe multi-process ledger with external anchor, Postgres, object storage with retention, versioned models and thresholds. |
| Solution | 35 | **85+** | Trained detectors, a labeled test set, calibrated scores, an UNSURE path, published error rates, a monthly refresh. |

A literal 100 on detection is not reachable because new generators keep appearing. A measured and maintained 85 to 90 is the real target.

### Hard targets (numbers get locked in Phase 2 from the baseline; until then these are the rules)
- Every score means something: "85" matches about 85% real on the held-out test set.
- Weak evidence gives `UNSURE` and human review. Never default-approve.
- No signal adds positive evidence without evidence. A failed or empty signal carries zero weight.
- False-approval rate and false-alarm rate are published per media type and per generator.
- The ledger survives two writers at once with no fork, and detects deleted tail rows.
- 50 simultaneous uploads: API stays responsive, no 5xx.
- No user media in git. Media is deleted after the retention period; hashes and reports stay.

### Definition of "100 out of 100" (in practice)
1. Problem: spec approved with buyer, workflow, cost of errors, and competitor edge.
2. Architecture: all Phase 3 exit criteria pass under load and under two workers.
3. Solution: locked test split meets the target error rates, calibration curve published, adversarial drop recorded, monthly refresh run at least once.

---

## 4. How we get there (summary of the plan)

Order rule: **measure first, then build models.** No training before the Phase 2 test set exists.

| Phase | Name | Weeks | Result |
|---|---|---|---|
| 0 | Stabilize | 1 | Clean repo, pinned deps, passing tests, no media in git, honest error handling. |
| 1 | Sharpen the problem | 1-2 | Niche, buyer, metrics and scope written down. |
| 2 | Evaluation first | 2-4 | Labeled dataset, locked test split, eval harness, honest baseline. |
| 3 | Architecture upgrade | 3-7 | Postgres, Celery and Redis jobs, safe ledger with anchor, storage retention, versioning. |
| 4 | Detection upgrade | 5-12 | Real C2PA, trained image/video/audio detectors, calibrated fusion, UNSURE, adversarial tests. |
| 5 | Product and frontend | 9-13 | Job status UI, plain explanations, review queue, verify-by-hash page, accuracy dashboard. |
| 6 | Operations | 12-16, then ongoing | Monitoring, drift checks, monthly refresh, runbooks, security pass, load test. |

Full detail:
- Master plan: `docs/plan/00-MASTER-PLAN.md`
- Phase files: `docs/plan/phase-0-stabilize.md` … `phase-6-operations.md`
- Audit findings mapped to phases: `docs/plan/audit-findings.md`
- Live progress and open questions: `docs/plan/STATUS.md` (update after every finished task)

### Who does what
- **Claude:** all code, tests, harnesses, docs, runbooks.
- **User:** niche and buyer, real and fake media, GPU or compute, acceptable error rates, final calls on product choices.
- If a task needs any of the user's items, stop and ask. Never invent data. Never train on the heuristics' own outputs.

---

## 5. Architecture target

```
Client -> API (FastAPI) -> save file (object storage) -> job queue (Redis/Celery)
                                                              |
                                              workers: signal plugins (time-limited)
                                                              |
                                         fusion + calibration -> verdict (or UNSURE)
                                                              |
                                  ledger writer (single writer, seq, versioned hash, anchor)
                                                              |
                                         Postgres  +  external head-hash anchor
Client polls /jobs/{id} -> report -> verify page (chain proof)
```

Design rules:
- Signals are stateless plugins behind `ISignalPlugin`. They never touch the database.
- Only the ledger writer writes ledger rows. Rows are append-only. Re-scoring adds new rows.
- Every row records `model_version`, `thresholds_version`, `pipeline_version` and `hash_version`.
- Media is deleted after retention. The hash and report stay.

---

## 6. Execution rules

1. Do not start a phase until the user says "start phase N".
2. Work phases in order. Phases 3 and 4 may overlap only after Phase 2 exits.
3. Before each task: read the phase file, then the code it names. Do not guess.
4. Make surgical changes. One task per commit-sized diff.
5. Mark a task done in `STATUS.md` only with proof: test output, build output, or exact diff.
6. If a task needs data, a GPU, a paid service or a product decision, stop and ask.
7. Do not commit or push unless the user asks. Never work on `main`; create a branch `phase-N-<name>` first.
8. Never put user media in git. Never log or store raw exception text in the ledger or return it to clients.
9. Before calling a phase done: tests, lint and typecheck pass, `securitymaxxing:diff` is clean, `STATUS.md` updated, scores re-estimated.

---

## 7. Commands

Backend (run from `backend/`):
```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m uvicorn app.main:app --reload --port 8000
```
Frontend (run from `frontend/`):
```bash
npm install
npm run dev
npm run lint
npm run build
```
Both servers on Windows: `./s.ps1`

---

## 8. Code rules

- Zero TypeScript errors, zero lint errors, no broken imports.
- Validate input at the API boundary. Handle errors defensively. Return fixed error messages to clients; log details on the server.
- A failed signal must carry zero weight (`confidence=0`). It must never score 0 with confidence 1.
- The ledger hash payload must stay deterministic. Changing it needs a `hash_version` bump and a verifier for old rows.
- Stored file extensions come from a fixed MIME map, never from the client filename.
- Use absolute paths for the database and storage. Never depend on the working directory.
- Add a dependency only when native code cannot do the job. Pin exact versions.
- Every new logic branch needs a test that fails when it breaks.
- Do not disable TLS verification. Do not unset `HTTPS_PROXY`.

## 9. Definition of done (per task)

- Code change made and checked against the phase file.
- Tests added or updated and passing (show output).
- Lint and typecheck clean (show output).
- Security skill check done for any route, upload, path, query or model code.
- `docs/plan/STATUS.md` updated.
- Anything not verified is stated in the report.

## 10. Known hazards

- `pytest` on this machine can crash on temp cleanup (`PermissionError` in `pytest-of-jaswa`). Use `--basetemp=.pytest_tmp`.
- `backend/storage/` and `*.db` were committed by mistake. Phase 0 stops tracking them.
- Python here is 3.14. Target runtime is 3.12. Check library wheels before adding ML packages.
- The working tree is far ahead of `HEAD`: signals were refactored into `heuristic_signals.py`. Commit on a branch before large changes.

## 11. Related files

- `backend/CLAUDE.md` — backend layout and rules.
- `frontend/CLAUDE.md` — frontend layout and rules.
- Legacy docs (`AUTHENTITRACE_25_PAGE_MASTER_DOCUMENTATION.md`, `COMPLETE_TECHNICAL_DOCUMENTATION.md`, `gemini.md`) describe a stack that is not built. Phase 0 moves them to `docs/archive/`.
