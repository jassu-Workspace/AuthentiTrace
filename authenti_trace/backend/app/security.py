"""API-key authentication and request rate limits.

API_KEYS="alice:key-one,bob:key-two"   label:key pairs. The label becomes the caller's identity
                                       (stored as the reviewer on review decisions).
Unset API_KEYS means authentication is OFF. That is for local development only: startup logs a warning.

RATE_LIMIT_UPLOADS_PER_MINUTE (default 30) limits POST /jobs and POST /upload per caller.
RATE_LIMIT_PER_MINUTE         (default 300) limits every other endpoint per caller.
RATE_LIMIT_HEAVY_PER_MINUTE   (default 6) limits GET /dashboard/audit, which re-hashes the whole ledger.
REQUIRE_API_KEYS=true         refuse to start when API_KEYS is empty (set it in production).
Caller = API key label, else client IP. Behind a proxy, start uvicorn with --proxy-headers and
--forwarded-allow-ips set to the proxy, or every request will look like it comes from the proxy.

shortcut: limits are counted per API process. With several API processes each keeps its own count, so the
effective limit is multiplied; move the counters to Redis if you need an exact global limit.
"""
import hmac
import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

ANONYMOUS = "anonymous"
MAX_TRACKED_CALLERS = 10_000


def _parse_keys(raw: str) -> Dict[str, str]:
    """Return {key: label}. Entries without a colon use the key itself as the label's seed."""
    keys: Dict[str, str] = {}
    for i, entry in enumerate(e.strip() for e in raw.split(",") if e.strip()):
        label, _, key = entry.partition(":")
        if not key:
            label, key = f"key{i + 1}", entry
        keys[key] = label
    return keys


def api_keys() -> Dict[str, str]:
    return _parse_keys(os.getenv("API_KEYS", ""))


def auth_enabled() -> bool:
    return bool(api_keys())


async def require_api_key(request: Request) -> str:
    """Return the caller's identity, or raise 401. Compares in constant time."""
    keys = api_keys()
    if not keys:
        return ANONYMOUS
    supplied = request.headers.get("x-api-key", "")
    for key, label in keys.items():
        if hmac.compare_digest(supplied.encode(), key.encode()):
            return label
    raise HTTPException(status_code=401, detail="A valid API key is required.")


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0, now: Optional[float] = None) -> Optional[int]:
        """Record a hit. Returns None when allowed, else the seconds until the caller may retry."""
        if limit <= 0:
            return None  # 0 disables the limit
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return max(1, int(q[0] + window - now) + 1)
        q.append(now)
        if len(self.hits) > MAX_TRACKED_CALLERS:  # drop callers with no recent hits
            for k in [k for k, v in self.hits.items() if not v or v[-1] <= now - window]:
                del self.hits[k]
        return None


limiter = SlidingWindowLimiter()


def _caller(request: Request, identity: str) -> str:
    if identity != ANONYMOUS:
        return f"key:{identity}"
    return f"ip:{request.client.host if request.client else 'unknown'}"


def _enforce(request: Request, identity: str, bucket: str, limit: int) -> None:
    retry = limiter.check(f"{bucket}:{_caller(request, identity)}", limit)
    if retry is not None:
        raise HTTPException(status_code=429, detail="Too many requests.", headers={"Retry-After": str(retry)})


async def rate_limit_general(request: Request, identity: str = Depends(require_api_key)) -> str:
    _enforce(request, identity, "general", int(os.getenv("RATE_LIMIT_PER_MINUTE", "300")))
    return identity


async def rate_limit_heavy(request: Request, identity: str = Depends(require_api_key)) -> str:
    """For endpoints that walk the whole ledger. Default 6 per minute per caller."""
    _enforce(request, identity, "heavy", int(os.getenv("RATE_LIMIT_HEAVY_PER_MINUTE", "6")))
    return identity


async def rate_limit_uploads(request: Request, identity: str = Depends(require_api_key)) -> str:
    _enforce(request, identity, "uploads", int(os.getenv("RATE_LIMIT_UPLOADS_PER_MINUTE", "30")))
    return identity


def check_startup() -> None:
    """Fail closed in production: with REQUIRE_API_KEYS=true the server refuses to start without keys."""
    if auth_enabled():
        return
    if os.getenv("REQUIRE_API_KEYS", "").lower() in ("1", "true", "yes"):
        raise RuntimeError("REQUIRE_API_KEYS is set but API_KEYS is empty. Refusing to start without authentication.")
    logger.warning("API_KEYS is not set: authentication is OFF. Do not expose this server to the internet.")
