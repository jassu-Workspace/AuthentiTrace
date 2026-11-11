# Phase 6 — Operations and upkeep (weeks 12-16, then ongoing)

Goal: keep the scores from decaying. Owner: Claude for code and runbooks, user for review decisions. Branch: `phase-6-ops`.

## Tasks
- [x] 6.1 (Prometheus `/api/v1/ops/metrics`: jobs by status, oldest queued age, ledger head, anchor age, per-signal latency, verdict counts; `/api/v1/health`. Counters are per process.) Monitoring: queue depth, per-signal latency, error rate, score distribution, anchor age.
- [x] 6.2 (`python -m app.services.drift_check` exits 1 on alert; dashboard shows PSI. The fresh labeled sample part needs your data.) Drift check: weekly compare of score distributions plus a small fresh labeled sample. Alert on a drop.
- [x] 6.3 (`docs/runbooks/monthly-refresh.md`. A real cycle needs your data.) Monthly refresh runbook: add new generators to the dataset, re-run `eval/run_eval.py`, ship a new model only if the numbers hold.
- [x] 6.4 (`docs/runbooks/missed-fake-incident.md`) Missed-fake incident runbook: confirm, re-score affected records, notify, add to the dataset.
- [~] 6.5 (done: API keys, per-caller rate limits, byte-level file-type check, image size cap, key-hiding `/api` proxy, Dockerfiles, compose, `.env.example`, CI. NOT done: antivirus scanning of uploads, Docker run, external secret manager.) Security pass (not part of the rating but required before real users): login or API keys, rate limits, upload scanning, real file-type checks, Dockerfile, deploy scripts, secrets handling.
- [~] 6.6 (SQLite backup/restore/verify tool, tested; Postgres steps are documented only.) Backup and restore test for Postgres and the anchor file.
- [~] 6.7 (`scripts/load_test.py`; local numbers in `docs/plan/capacity.md`. Not run on target hardware, Postgres or large files.) Load test and record the capacity numbers.

## Exit criteria
- One full monthly refresh cycle completed.
- Restore test passes.
- Runbooks exist in `docs/runbooks/`.
