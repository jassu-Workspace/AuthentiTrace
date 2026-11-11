# Runbook: deploy

## First deploy (Docker Compose)
1. Copy `.env.example` to `.env`. Set `POSTGRES_PASSWORD`, `API_KEYS` (label:key pairs, long random keys) and `BACKEND_API_KEY` (one of those keys).
2. `docker compose up --build`. The API runs the database migrations at startup.
3. Check: `curl http://localhost:8000/api/v1/health` returns `{"status":"ok"}`. Open `http://localhost:3000`.
4. Put a TLS reverse proxy in front. Set `FORWARDED_ALLOW_IPS` to the proxy address so rate limits see real client IPs.
5. Set `MEDIA_RETENTION_DAYS` (for example 30). Copy `ledger_anchor.jsonl` to storage the database admin cannot write (see `restore.md`).

This compose file was not run where it was written (no Docker daemon). Expect to fix small things on the first run.

## Every release
1. CI green (backend tests and lint, frontend lint, type check and build).
2. Back up (see `restore.md`).
3. Deploy. The API applies pending migrations at startup. If a migration fails the API does not start: read the log, fix, redeploy.
4. Check `/api/v1/health`, `/api/v1/dashboard/audit` (`ledger_intact` must be true) and the review queue page.

## Rollback
Redeploy the previous image. Migrations are additive; do not run `alembic downgrade` on live data unless you tested it.

## Settings that change behavior
See `.env.example`. Scoring limits (`SCORING_MIN_EVIDENCE`, `SCORING_MAX_DISAGREEMENT`) are uncalibrated placeholders until you tune them with the evaluation harness.
