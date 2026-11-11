# Handoff: what is built, and what only you can do

Everything below the line "Needs you" cannot be finished by code alone. The numbers in `eval/thresholds.example.json`
are placeholders, not targets: set real ones after your first measurement.

## Built and tested
| Area | State |
|---|---|
| Ledger | sequence numbers, versioned hashes, fork guard, anchor file, batched audit, backup/restore tool |
| Jobs | `/api/v1/jobs` with polling; in-process runner or Celery + Redis workers (tested with 2 worker processes) |
| Storage | local or S3 (S3 tested with a mock); optional media retention |
| Detection rules | zero weight for "no evidence", abstain to human review, real C2PA check, registry matching |
| Trained model hook | ONNX detector via `IMAGE_MODEL_PATH` (tested with a tiny model) |
| Measurement | eval harness, split locking, attacks, calibration and fusion fitting (tested on synthetic data) |
| Product | job-status upload, plain-language report, review queue, verify page, quality dashboard, `/api` proxy that hides the key |
| Operations | API keys, rate limits, upload content checks, `/health`, Prometheus `/ops/metrics`, drift check, runbooks, Dockerfiles, compose, CI |

## Needs you (cannot be done by code)
0. **Put the web app behind a login.** It has none: the `/api` proxy gives every visitor the proxy key's rights (`docs/plan/security-review.md`, finding 1). Use SSO or basic auth at your reverse proxy before real users.
1. **Pick the niche and buyer.** Read `docs/spec/problem-spec.md`. The niche there is a placeholder.
2. **Provide labeled data.** Real and fake files with a `manifest.csv` (`backend/eval/README.md`). A few thousand, several generators, plus re-compressed and screenshot copies. Without it there is no accuracy number, and every score stays "uncalibrated".
3. **Run the baseline**, then set real limits in `eval/thresholds.json` and the Phase 1 metric targets (`docs/plan/baseline.md`).
4. **Train or choose a detector** (needs a GPU or cloud credits and a licence check on any model), export to ONNX, write the sidecar JSON, set `IMAGE_MODEL_PATH`. Then fit fusion and calibration (`monthly-refresh.md`). Video and audio detectors do not exist yet: those files go to human review.
5. **Fill the registries** (`backend/registry/README.md`) from sources you trust.
6. **Set secrets and deploy:** `.env` (never commit it), TLS reverse proxy, an off-box copy of the anchor file, `MEDIA_RETENTION_DAYS`. First run of `docker compose up` was never tried here (no Docker daemon): expect small fixes.
7. **Run once on real Postgres.** The code is written for it (`requirements-postgres.txt`) but was only tested on SQLite.
8. **Run an accessibility pass** (screen reader, keyboard-only) and a security review by a person before real users.
9. **Decide your policy on reviewer identity:** with `API_KEYS` set, the reviewer is the key's label. Give each reviewer their own key.
10. **Competitor research** (Phase 1.4) was not done.

## Known limits (be honest with users)
- Detection is still rule-based unless you add a model. A fake with its metadata stripped can still be approved.
- The abstain limits (`SCORING_MIN_EVIDENCE`, `SCORING_MAX_DISAGREEMENT`) and `DHASH_MAX_DISTANCE` are placeholders.
- The anchor file only helps if you copy it somewhere the database admin cannot write.
- Rate limits are counted per API process.
- Metrics counters are per process.
- Uploads are limited by the host in front of the proxy (for example about 4.5 MB on Vercel functions).
