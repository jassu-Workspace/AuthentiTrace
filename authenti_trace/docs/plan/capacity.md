# Capacity measurements

Local development machine, Windows 11, Python 3.14, one API process. Script: `backend/scripts/load_test.py`.
Test files: 50 synthetic 640x480 JPEGs. These are not production numbers.

| Setup | Uploads | All accepted | Time to done (p50 / p95) | Dashboard probe p95 during load | Ledger audit |
|---|---|---|---|---|---|
| SQLite, jobs run inside the API process | 50 at once | 50 of 50 (202) | 4.6 s / 5.4 s | 644 ms | intact |
| SQLite, Redis broker, API plus 2 Celery worker processes | 50 at once | 50 of 50 (202) | 8.3 s / 10.3 s | 39 ms | intact (50 rows, anchor at 50) |

Reading it: with workers in separate processes the API stays quick (39 ms) but total time is longer on this machine because Windows runs Celery with `-P solo` (one job at a time per worker). On Linux, `--concurrency N` runs N jobs per worker.

Not measured: Postgres, real file sizes up to 50 MB, video, the trained model, a cloud host. Measure these before you promise any capacity. Repeat with `python scripts/load_test.py --n 200` on the target hardware.
