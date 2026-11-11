"""Score-distribution drift (Population Stability Index) and a simple histogram.

CLI for cron or CI (exit code 1 on alert):  python -m app.services.drift_check
"""
import math
from datetime import timedelta
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ledger import VerificationRecord, utcnow

PSI_WATCH = 0.10  # common rule of thumb: above 0.10 look at it, above 0.25 act
PSI_ALERT = 0.25
MIN_SAMPLES = 30


def histogram(scores: Sequence[float], bins: int = 10) -> List[int]:
    counts = [0] * bins
    for s in scores:
        counts[min(int(max(s, 0.0) / (100 / bins)), bins - 1)] += 1
    return counts


def psi(baseline: Sequence[float], recent: Sequence[float], bins: int = 10) -> Optional[float]:
    """PSI of the recent scores against the baseline scores. None when either side is too small to trust."""
    if len(baseline) < MIN_SAMPLES or len(recent) < MIN_SAMPLES:
        return None
    eps = 1e-4
    total = 0.0
    for b, r in zip(histogram(baseline, bins), histogram(recent, bins)):
        pb, pr = max(b / len(baseline), eps), max(r / len(recent), eps)
        total += (pr - pb) * math.log(pr / pb)
    return round(total, 4)


def drift_status(value: Optional[float]) -> str:
    if value is None:
        return "insufficient_data"
    return "alert" if value >= PSI_ALERT else "watch" if value >= PSI_WATCH else "stable"


async def score_windows(db: AsyncSession, window_days: int = 7) -> Tuple[List[float], List[float]]:
    """(baseline, recent) verification scores: the window before the last window_days days, and that window."""
    now = utcnow()
    recent_from = now - timedelta(days=window_days)
    rows = (await db.execute(
        select(VerificationRecord.composite_score, VerificationRecord.created_at).where(
            VerificationRecord.risk_category != "REVIEWED",
            VerificationRecord.created_at >= now - timedelta(days=2 * window_days),
        )
    )).all()
    recent = [s for s, at in rows if at >= recent_from and s is not None]
    baseline = [s for s, at in rows if at < recent_from and s is not None]
    return baseline, recent
