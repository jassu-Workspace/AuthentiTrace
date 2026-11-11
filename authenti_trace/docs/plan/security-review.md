# Security review of branch phase-6-ops (diff review)

Scope: security-relevant code added since Phase 3: `security.py`, `media_service.py`, `object_store.py`, `backup.py`, `ledger_service.py`,
all endpoints, `provenance.py`, `onnx_detector.py`, the `/api` proxy route, `api.ts`, Dockerfiles, `docker-compose.yml`.
Method: read each changed function with its callers and the router it is mounted on; ran the real proxy against a keyed backend.
Not done: dependency vulnerability scan (no scanner available offline), fuzzing, penetration test, review by a second person.

**Verdict: Safe to merge with follow-ups.** No hard-coded secrets, no injection sinks, every router except `/health` sits behind the key check.
The blocking item for a public deployment is the missing user login on the web app (finding 1).

## Blocking for a public deployment (not for merging)
1. **The web app has no user login, and its proxy turns every visitor into an authenticated caller** (`frontend/src/app/api/[...path]/route.ts`).
   - Problem: the API key protects the backend, but the proxy adds that key to every request. Anyone who can open the web page can upload, approve or reject reviews (as the proxy key's identity), and read all reports.
   - Fix (not code): put the web app behind SSO or basic auth at the reverse proxy until a login is built. Give reviewers their own access path. This is listed in `docs/HANDOFF.md`.

## Fixed in this review
2. **Fails open when keys are missing** (`security.py`). A deployment that forgot `API_KEYS` ran with no authentication and only a log warning. Now `REQUIRE_API_KEYS=true` stops startup; compose sets it. Test added.
3. **Ledger audit could be called 300 times a minute** (`dashboard.py`). Each call re-hashes the whole chain. Now limited to 6 per minute per caller (`RATE_LIMIT_HEAVY_PER_MINUTE`). Test added.
4. **Large images could exhaust memory in analysis** (`media_service.py`). Default pixel cap lowered from 50M to 25M; analysis makes several full-size float copies. Tune with `MAX_IMAGE_PIXELS` and limit worker concurrency.
5. **API port published by compose** (`docker-compose.yml`). The API is now reachable only through the web service by default.

## Non-blocking follow-ups
6. **Shared rate-limit budget.** With auth on, all browser users share the web key's bucket, so one heavy user can use up everyone's uploads. I did not key by IP because the proxy forwards the client's `X-Forwarded-For`, which a client can fake when the web server is directly exposed. Put a per-IP limit at the reverse proxy and raise `RATE_LIMIT_UPLOADS_PER_MINUTE`.
7. **File parsers see hostile input.** The byte check (`matches_declared_type`) is shallow (an MP4 only needs `ftyp`; MP3 only a sync byte). Videos go to OpenCV/FFmpeg, images to Pillow. Run workers as the unprivileged user (done in the Dockerfile), with no secrets in their environment other than what they need, and keep the libraries updated.
8. **Rows in the database decide which file paths a worker reads or deletes** (`object_store.py` `LocalStore`). Only someone who can already write the database can abuse it. Keep database credentials limited to the API and workers.
9. **Reviewer name is self-asserted when `API_KEYS` is not set** (`reviews.py`). With keys on, it comes from the key label. Do not run reviews without keys.
10. **The anchor file is a shortcut** (`ledger_service.py`): copy it off the database host (see `docs/runbooks/restore.md`).
11. **Per-process rate limits and metrics.** Several API processes multiply the effective limit.
12. **Docker and compose were not run.** Secrets pass through environment variables (visible with `docker inspect`); use your platform's secret store if you have one.
13. **Percent-encoded `..` in the proxy path** (`%2e%2e`) passes the proxy's segment check. It only reaches the backend's own router, which has no file serving, so it ends in a 404, but strip it anyway when you next touch the file.
