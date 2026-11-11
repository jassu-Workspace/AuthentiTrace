# Runbook: a fake was approved (or a real file was blocked)

1. **Confirm.** Open the report (`/report/<id>`) and the verify page (`/verify?id=<id>`). Confirm the record is intact. If the proof fails, treat it as a tampering incident instead and stop here: preserve the database and anchor file, then follow `restore.md`.
2. **Record the human decision.** Open the review queue or call `POST /api/v1/reviews/<id>` with `reject` (or `approve`) and a note. This adds a new ledger row. The original row stays as it was, which is the point.
3. **Find the same file.** Search by hash on the verify page, or `GET /api/v1/reports/by-hash/<sha256>`. List every record for it and for near copies you can identify.
4. **Notify.** Tell the people or systems that relied on the verdict. Give the record ids and the corrected decision.
5. **Add to the dataset.** Put the file in `backend/eval/data/` with `label` set correctly and a `source` and `generator` if known. It goes into the next monthly refresh (`monthly-refresh.md`). Do not put it only in the test split by hand: use `make_splits`.
6. **Find out why it was missed.** Open the per-signal results. Which signals were silent (no evidence), which were confident and wrong? Did an attack change the verdict (`run_attacks`)? Write the cause in `docs/plan/STATUS.md`.
7. **Add to the registries if it spreads.** Append the SHA-256 to `backend/registry/malicious_sha256.txt` and the dHash to `synthetic_dhash.txt` (one per line). Restart the API. Known copies are then caught at once.
8. **Re-score if the pipeline changed.** `python -m app.services.rescore`.
