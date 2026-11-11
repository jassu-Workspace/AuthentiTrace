"""Small Prometheus-format metrics. Counters live in this process; gauges are read from the database on scrape.

shortcut: counters are per process (reset on restart, not shared between API and Celery workers).
Use them for rates and trends in each process; the database gauges (queue depth, ledger head) are global.
"""
import threading
import time
from collections import defaultdict
from typing import Dict, Tuple

_lock = threading.Lock()
_counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)


def inc(name: str, amount: float = 1.0, **labels: str) -> None:
    with _lock:
        _counters[(name, tuple(sorted(labels.items())))] += amount


def observe(name: str, seconds: float, **labels: str) -> None:
    """Records a duration as a _sum and _count pair (enough for an average and a rate)."""
    inc(f"{name}_seconds_sum", seconds, **labels)
    inc(f"{name}_seconds_count", 1.0, **labels)


def _fmt(name: str, labels: Tuple[Tuple[str, str], ...], value: float) -> str:
    if labels:
        body = ",".join(f'{k}="{str(v).replace(chr(92), "").replace(chr(34), "")}"' for k, v in labels)
        return f"{name}{{{body}}} {value:g}"
    return f"{name} {value:g}"


def render(gauges: Dict[str, float]) -> str:
    with _lock:
        counter_lines = [_fmt(n, lb, v) for (n, lb), v in sorted(_counters.items())]
    gauge_lines = [f"{n} {v:g}" for n, v in sorted(gauges.items())]
    return "\n".join(counter_lines + gauge_lines + [f"authentitrace_scrape_time_seconds {time.time():.0f}", ""])


def reset() -> None:
    with _lock:
        _counters.clear()
