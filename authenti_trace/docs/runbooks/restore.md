# Runbook: backup and restore

What must be backed up: the database, the ledger anchor file (`LEDGER_ANCHOR_PATH`), and, if you need to re-score, the media (`STORAGE_DIR` or the S3 bucket).

## SQLite
Backup (safe while the API runs):
```bash
python -m app.services.backup backup --to backups/2026-01-15
```
Restore into new files, then verify before you switch the API over:
```bash
python -m app.services.backup restore --from backups/2026-01-15 --db restored.db --anchor restored_anchor.jsonl
python -m app.services.backup verify --db restored.db --anchor restored_anchor.jsonl
```
`restore` refuses a backup whose checksums changed. `verify` exits 1 if any row, link or anchor entry is wrong. Only a restore that passes `verify` goes live.

## Postgres
```bash
pg_dump -Fc -h HOST -U USER authentitrace > backups/2026-01-15.dump
pg_restore -h HOST -U USER -d authentitrace_restored backups/2026-01-15.dump
```
Copy `ledger_anchor.jsonl` into the same backup folder. After a restore, point a throwaway API at the restored database with the matching anchor file and call `/api/v1/dashboard/audit`.

## The anchor file protects against deleted records
Anyone who can change both the database and the anchor file can rewrite history. Copy the anchor file regularly to storage the database admin cannot write to (object storage with versioning and object lock, or a separate account). Compare the newest copy with the live file during audits.

## Restore test (do this every quarter)
1. Take a backup. 2. Restore it to a scratch location. 3. Run `verify`. 4. Write the date and result in `docs/plan/STATUS.md`.
