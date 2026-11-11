"""Pure metric functions for the evaluation harness. No I/O, stdlib only.

Definitions (a row is one evaluated file):
- label: "real" or "fake" (ground truth)
- action: APPROVE | FLAG | RESTRICT | MANUAL_REVIEW (system output)
- false approval: label == fake and action == APPROVE
- false alarm:    label == real and action in {FLAG, RESTRICT}
- unsure:         action == MANUAL_REVIEW (counted separately, in neither error)
"""
from collections import defaultdict
from typing import Any, Dict, Iterable, List

Row = Dict[str, Any]

ALARM_ACTIONS = {"FLAG", "RESTRICT"}


def _rate(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def false_approval_rate(rows: Iterable[Row]) -> float | None:
    fakes = [r for r in rows if r["label"] == "fake"]
    return _rate(sum(r["action"] == "APPROVE" for r in fakes), len(fakes))


def false_alarm_rate(rows: Iterable[Row]) -> float | None:
    reals = [r for r in rows if r["label"] == "real"]
    return _rate(sum(r["action"] in ALARM_ACTIONS for r in reals), len(reals))


def unsure_rate(rows: Iterable[Row]) -> float | None:
    rows = list(rows)
    return _rate(sum(r["action"] == "MANUAL_REVIEW" for r in rows), len(rows))


def by_group(rows: Iterable[Row], key: str) -> Dict[str, Dict[str, Any]]:
    """Per-group counts and error rates (group by media_type, generator, transform, ...)."""
    groups: Dict[str, List[Row]] = defaultdict(list)
    for r in rows:
        groups[str(r.get(key) or "unknown")].append(r)
    return {
        name: {
            "n": len(g),
            "false_approval_rate": false_approval_rate(g),
            "false_alarm_rate": false_alarm_rate(g),
            "unsure_rate": unsure_rate(g),
        }
        for name, g in sorted(groups.items())
    }


def calibration_bins(rows: Iterable[Row], bins: int = 10) -> List[Dict[str, Any]]:
    """Calibration check: files scored in a bin should be real about as often as the score says.

    expected = mean score / 100 (the system's claimed probability real)
    observed = share of truly real files in the bin
    """
    buckets: Dict[int, List[Row]] = defaultdict(list)
    for r in rows:
        idx = min(int(float(r["score"]) / (100 / bins)), bins - 1)
        buckets[idx].append(r)
    out = []
    for idx in sorted(buckets):
        g = buckets[idx]
        expected = sum(float(r["score"]) for r in g) / len(g) / 100
        observed = sum(r["label"] == "real" for r in g) / len(g)
        out.append({
            "bin": f"{idx * 100 // bins}-{(idx + 1) * 100 // bins}",
            "n": len(g),
            "expected_real": round(expected, 4),
            "observed_real": round(observed, 4),
            "gap": round(abs(expected - observed), 4),
        })
    return out


def latency_percentiles(rows: Iterable[Row]) -> Dict[str, float | None]:
    values = sorted(float(r["latency_s"]) for r in rows)
    if not values:
        return {"p50": None, "p95": None, "max": None}

    def pct(p: float) -> float:
        return round(values[min(int(p * len(values)), len(values) - 1)], 4)

    return {"p50": pct(0.50), "p95": pct(0.95), "max": round(values[-1], 4)}


def summarize(rows: List[Row]) -> Dict[str, Any]:
    return {
        "n": len(rows),
        "false_approval_rate": false_approval_rate(rows),
        "false_alarm_rate": false_alarm_rate(rows),
        "unsure_rate": unsure_rate(rows),
        "by_media_type": by_group(rows, "media_type"),
        "by_generator": by_group(rows, "generator"),
        "by_transform": by_group(rows, "transform"),
        "calibration": calibration_bins(rows),
        "latency_s": latency_percentiles(rows),
    }


def check_thresholds(summary: Dict[str, Any], thresholds: Dict[str, float]) -> List[str]:
    """Return human-readable failures. Thresholds are upper bounds; a missing metric (None) fails."""
    failures = []
    for key, limit in thresholds.items():
        value = summary.get(key)
        if value is None:
            failures.append(f"{key}: no data (limit {limit})")
        elif value > limit:
            failures.append(f"{key}: {value} > {limit}")
    return failures
