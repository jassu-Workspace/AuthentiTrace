# AuthentiTrace

Checks whether uploaded media (image, video, audio) is likely authentic, and records each verdict in a hash-chained ledger so later edits are detectable.

**Status:** prototype. Detection is rule-based (no trained model yet) and scores are not calibrated. Do not use the verdict as proof. See the plan below.

## How it works
1. `POST /api/v1/jobs/` saves the file, computes its SHA-256 and returns `202` with a job id. Poll `GET /api/v1/jobs/{id}`; when `done` it carries the report id. (`POST /api/v1/upload/` is the older blocking version; the UI still uses it until Phase 5.)
2. Five signal plugins score the file in worker threads, each with a timeout: Content, Reality, Behavioral, Network, Integrity.
3. A scoring engine combines them into a trust score, a risk category and an action (`APPROVE`, `FLAG`, `RESTRICT`, or `MANUAL_REVIEW` when no signal has evidence).
4. The result is appended to a SQLite ledger. Each row has a sequence number, and its hash covers the previous row, its time and the pipeline versions. Every new head is also written to an anchor file.
5. `GET /api/v1/reports/{id}` returns a report. `GET /api/v1/dashboard/audit` re-walks the chain and compares it with the anchor file, so edited, missing or truncated rows are reported.

## Run it
Backend (Python):
```bash
cd authenti_trace/backend
python -m pip install -r requirements-dev.txt
python -m pytest -q   # use --basetemp=.pytest_tmp if Windows temp cleanup fails
python -m uvicorn app.main:app --reload --port 8000
```
Frontend (Node):
```bash
cd authenti_trace/frontend
npm install
npm run dev
```
Both on Windows: `authenti_trace/s.ps1`.

## Configuration
| Variable | Used by | Default |
|---|---|---|
| `DATABASE_URL` | backend | `sqlite+aiosqlite:///<backend>/authentitrace.db` |
| `STORAGE_DIR` | backend | `<backend>/storage` |
| `CORS_ALLOW_ORIGINS` | backend | `http://localhost:3000,http://127.0.0.1:3000` |
| `LEDGER_ANCHOR_PATH` | backend | `<backend>/ledger_anchor.jsonl` (empty disables). Delete it together with the database. |
| `MEDIA_RETENTION_DAYS` | backend | `0` (keep forever). Set `30` or your policy in production. |
| `SIGNAL_TIMEOUT_SECONDS` | backend | `60` |
| `JOB_MAX_ATTEMPTS` | backend | `2` |
| `NEXT_PUBLIC_API_URL` | frontend | `http://127.0.0.1:8000` in dev; relative paths in production if unset |

## Database
Schema changes are Alembic migrations in `backend/alembic/versions`. The API applies them at startup. Manual: `cd backend && python -m alembic upgrade head`. Old databases are upgraded in place (old rows keep their original hashes, `hash_version` 1).

Re-score stored media under the current pipeline version (appends new rows, never edits old ones): `python -m app.services.rescore`.

## Layout
- `authenti_trace/backend/app` — API, services, signal plugins, ledger.
- `authenti_trace/frontend/src` — Next.js pages and API helper.
- `authenti_trace/docs/plan` — master plan, phases 0-6, status.
- `authenti_trace/docs/archive` — old documents. They describe a stack that is not built.
- `authenti_trace/CLAUDE.md` — goals, targets and working rules.

## Roadmap
See `authenti_trace/docs/plan/00-MASTER-PLAN.md` and `authenti_trace/docs/plan/STATUS.md`.
