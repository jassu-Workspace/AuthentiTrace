"""Load test: many simultaneous uploads, then wait for every job and audit the ledger.

Usage (server must be running; from backend/):
    python scripts/load_test.py --base http://127.0.0.1:8000/api/v1 --n 50 [--api-key KEY]

Prints: submit status codes, time-to-done percentiles, latency of a cheap endpoint during the load,
and the ledger audit. Numbers depend on the machine: record them with the hardware and settings used.
"""
import argparse
import asyncio
import io
import statistics
import time

import httpx
import numpy as np
from PIL import Image


def make_jpeg(seed: int) -> bytes:
    arr = np.random.default_rng(seed).normal(128, 40, (480, 640, 3)).clip(0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG", quality=90)
    return buf.getvalue()


async def main(base: str, n: int, api_key: str, timeout_s: int) -> None:
    headers = {"X-API-Key": api_key} if api_key else {}
    files = [make_jpeg(i) for i in range(n)]
    async with httpx.AsyncClient(timeout=120, headers=headers) as c:
        probe, stop = [], False

        async def probe_loop():
            while not stop:
                t = time.perf_counter()
                r = await c.get(f"{base}/dashboard/metrics")
                probe.append((time.perf_counter() - t, r.status_code))
                await asyncio.sleep(0.2)

        probe_task = asyncio.create_task(probe_loop())
        t0 = time.perf_counter()
        resps = await asyncio.gather(*[
            c.post(f"{base}/jobs/", files={"file": (f"{i}.jpg", files[i], "image/jpeg")}) for i in range(n)])
        codes = [r.status_code for r in resps]
        ids = [r.json()["job_id"] for r in resps if r.status_code == 202]

        done, deadline = {}, time.perf_counter() + timeout_s
        while len(done) < len(ids) and time.perf_counter() < deadline:
            for jid in ids:
                if jid not in done:
                    s = (await c.get(f"{base}/jobs/{jid}")).json()
                    if s["status"] in ("done", "failed"):
                        done[jid] = (time.perf_counter() - t0, s["status"])
            await asyncio.sleep(0.5)
        stop = True
        await probe_task
        audit = (await c.get(f"{base}/dashboard/audit")).json()

    times = sorted(v[0] for v in done.values())
    lat = sorted(x for x, _ in probe)
    print("submit codes:", {k: codes.count(k) for k in set(codes)})
    print("jobs:", {s: [v[1] for v in done.values()].count(s) for s in {v[1] for v in done.values()}}, f"of {len(ids)}")
    if times:
        print(f"time-to-done p50={statistics.median(times):.1f}s p95={times[max(int(.95 * len(times)) - 1, 0)]:.1f}s max={times[-1]:.1f}s")
    if lat:
        print(f"probe /metrics during load: p50={lat[len(lat)//2]*1000:.0f}ms p95={lat[max(int(.95*len(lat))-1,0)]*1000:.0f}ms max={lat[-1]*1000:.0f}ms")
    print("audit:", {k: audit[k] for k in ("ledger_intact", "chain_length", "errors_total")})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--api-key", default="")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    asyncio.run(main(args.base, args.n, args.api_key, args.timeout))
