# Phase 0 — Stabilize (week 1)

Goal: a clean, reproducible base. Owner: Claude. Branch: `phase-0-stabilize`.

## Tasks
- [x] 0.1 Inspect `git status`. Commit current work on the branch in logical commits (only when the user asks): signals refactor, tests, deletions, frontend changes.
- [x] 0.2 Create root `.gitignore`: `storage/`, `backend/storage/`, `*.db`, `__pycache__/`, `.pytest_cache/`, `.pytest_tmp/`, `graphify-out/`, `outputs/`, `.env*`.
- [x] 0.3 `git rm -r --cached backend/storage backend/authentitrace.db authentitrace.db`. Ask the user before rewriting history to purge old media (filter-repo). Default: stop tracking only.
- [x] 0.4 Make the DB path absolute in `backend/app/database/database.py` (env `DATABASE_URL`, default next to `backend/`). Same for `STORAGE_DIR` in `media_service.py`.
- [x] 0.5 Pin exact versions in `backend/requirements.txt`. Create `requirements-dev.txt` with pytest, pytest-asyncio, httpx.
- [x] 0.6 Get `python -m pytest -q` passing. Use `--basetemp=.pytest_tmp` if temp cleanup crashes.
- [x] 0.7 Remove the dead integrity re-hash in `integrity.py`. Keep only the blacklist lookup.
- [x] 0.8 Remove unused imports across `backend/app`.
- [x] 0.9 Replace `str(e)` in `upload.py` and `verification_service.py` metadata with fixed messages. Log details with `logging`.
- [x] 0.10 Plugin crash handling: `score=50, confidence=0` and `metadata={"error": "<ExceptionClassName>"}` in `verification_service.py`.
- [x] 0.11 Extension from a fixed MIME map in `media_service.py`. Delete the file on any failure in the save path and in `process_verification` errors.
- [x] 0.12 Confirm frontend production API URL behavior (`frontend/src/lib/api.ts`, `VERCEL_DEPLOYMENT.md`).
- [x] 0.13 Replace long legacy docs with a short `README.md` that matches the code. Move old docs to `docs/archive/`.

## Exit criteria
- Fresh clone: install, tests pass, app starts.
- `git ls-files` shows no media and no `.db`.
- `npm run lint` and `npm run build` pass.
- Audit findings 1, 5, 7, 9, 10, 12, 13, 14 closed (see `audit-findings.md`).
