# Phase 6 — Operations and upkeep (weeks 12-16, then ongoing)

Goal: keep the scores from decaying. Owner: Claude for code and runbooks, user for review decisions. Branch: `phase-6-ops`.

## Tasks
- [ ] 6.1 Monitoring: queue depth, per-signal latency, error rate, score distribution, anchor age.
- [ ] 6.2 Drift check: weekly compare of score distributions plus a small fresh labeled sample. Alert on a drop.
- [ ] 6.3 Monthly refresh runbook: add new generators to the dataset, re-run `eval/run_eval.py`, ship a new model only if the numbers hold.
- [ ] 6.4 Missed-fake incident runbook: confirm, re-score affected records, notify, add to the dataset.
- [ ] 6.5 Security pass (not part of the rating but required before real users): login or API keys, rate limits, upload scanning, real file-type checks, Dockerfile, deploy scripts, secrets handling.
- [ ] 6.6 Backup and restore test for Postgres and the anchor file.
- [ ] 6.7 Load test and record the capacity numbers.

## Exit criteria
- One full monthly refresh cycle completed.
- Restore test passes.
- Runbooks exist in `docs/runbooks/`.
