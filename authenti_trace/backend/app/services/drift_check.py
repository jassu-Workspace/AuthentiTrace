"""Print the score drift status and exit 1 on alert. Run it from cron or a scheduled job.

Usage (from backend/):  python -m app.services.drift_check [--window-days 7]
Exit codes: 0 stable, watch or not enough data; 1 alert.
"""
import argparse
import asyncio
import json
import sys

from app.database.database import SessionLocal
from app.services.drift import drift_status, psi, score_windows


async def main(window_days: int) -> int:
    async with SessionLocal() as db:
        baseline, recent = await score_windows(db, window_days)
    value = psi(baseline, recent)
    status = drift_status(value)
    print(json.dumps({"psi": value, "status": status, "baseline_n": len(baseline), "recent_n": len(recent),
                      "window_days": window_days}))
    return 1 if status == "alert" else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window-days", type=int, default=7)
    sys.exit(asyncio.run(main(ap.parse_args().window_days)))
