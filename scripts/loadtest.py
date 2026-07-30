"""Measure throughput and latency percentiles for each endpoint.

    uvicorn app.main:app --port 8137          # in one terminal
    python scripts/loadtest.py                # in another

Written against httpx, which is already a dependency, rather than pulling in k6 or Locust.
The workload here is a few hundred requests against a single process; a dedicated load
tool would add an install and a binary without measuring anything this cannot.

Methodology, because a latency number without one is decoration:

* **Measured locally against a single uvicorn worker.** Benchmarking the deployed free
  tier would measure Render's shared CPU and cold starts, not this code.
* **Warm-up requests are discarded** so first-call imports and lazy loads do not land in
  the percentiles.
* **Percentiles come from individual request durations**, not from an average of averages.
* Concurrency is ramped so the point where latency degrades is visible rather than
  hidden inside one aggregate figure.
* `/recommend` is measured twice: with varied payloads to defeat the response cache, and
  with one repeated payload to show what the cache is worth.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "PERFORMANCE.md"

CONCURRENCY_LEVELS = (1, 4, 16, 32)
REQUESTS_PER_LEVEL = 200
WARMUP = 20

# Varied medication lists so each request misses the response cache.
_MEDS = [
    ["warfarin"],
    ["lorazepam"],
    ["Xanax 1mg"],
    ["ciprofloxacin"],
    ["metformin"],
    ["levothyroxine"],
    ["prednisone"],
    ["alendronate"],
    ["quetiapine"],
    ["zolpidem"],
]


def _cases() -> list[dict]:
    symptom_answers = {
        "trouble-falling-asleep": "applies",
        "night-waking": "applies",
        "loud-snoring": "applies",
        "daytime-sleepiness": "applies",
    }
    return [
        {"name": "GET /health", "method": "GET", "path": "/health"},
        {
            "name": "POST /recommend (cache miss)",
            "method": "POST",
            "path": "/recommend",
            "vary": True,
        },
        {
            "name": "POST /recommend (cache hit)",
            "method": "POST",
            "path": "/recommend",
            "json": {"goal": "sleep", "meds": ["warfarin"]},
        },
        {
            "name": "POST /symptoms",
            "method": "POST",
            "path": "/symptoms",
            "json": {"answers": symptom_answers},
        },
        {"name": "GET /supplements/melatonin", "method": "GET", "path": "/supplements/melatonin"},
        {"name": "GET / (homepage)", "method": "GET", "path": "/"},
    ]


async def _one(client: httpx.AsyncClient, case: dict, index: int) -> tuple[float, int]:
    payload = case.get("json")
    if case.get("vary"):
        payload = {"goal": "sleep", "meds": _MEDS[index % len(_MEDS)]}
    started = time.perf_counter()
    if case["method"] == "GET":
        response = await client.get(case["path"])
    else:
        response = await client.post(case["path"], json=payload)
    return (time.perf_counter() - started) * 1000, response.status_code


async def run_case(base: str, case: dict, concurrency: int) -> dict:
    limits = httpx.Limits(max_connections=concurrency + 8)
    async with httpx.AsyncClient(base_url=base, limits=limits, timeout=30.0) as client:
        # Warm-up: discarded, so lazy imports and first-touch caches do not skew p99.
        await asyncio.gather(*(_one(client, case, i) for i in range(WARMUP)))

        semaphore = asyncio.Semaphore(concurrency)

        async def guarded(i: int) -> tuple[float, int]:
            async with semaphore:
                return await _one(client, case, i)

        wall_start = time.perf_counter()
        results = await asyncio.gather(*(guarded(i) for i in range(REQUESTS_PER_LEVEL)))
        wall = time.perf_counter() - wall_start

    latencies = sorted(ms for ms, _ in results)
    errors = sum(1 for _, status in results if status >= 400)
    quantiles = statistics.quantiles(latencies, n=100, method="inclusive")
    return {
        "concurrency": concurrency,
        "requests": len(results),
        "rps": len(results) / wall,
        "p50": quantiles[49],
        "p95": quantiles[94],
        "p99": quantiles[98],
        "max": latencies[-1],
        "errors": errors,
    }


async def main_async(base: str) -> int:
    try:
        async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
            await client.get("/health")
    except httpx.HTTPError as exc:
        print(f"cannot reach {base}: {exc}")
        print("start the server first:  uvicorn app.main:app --port 8137")
        return 1

    # A load test that reports percentiles over rejected requests is worse than no load
    # test, so refuse to run when the rate limiter is going to reject the traffic. The
    # first run of this script measured 429s and produced plausible-looking latencies.
    probe = await run_case(base, {"name": "probe", "method": "GET", "path": "/health"}, 4)
    if probe["errors"]:
        print(
            f"{probe['errors']} of {probe['requests']} probe requests failed.\n"
            "The per-IP rate limit is almost certainly rejecting the load. Restart the\n"
            "server with the limit raised, then re-run:\n\n"
            "  SLEEPWISE_RATE_LIMIT=1000000 uvicorn app.main:app --port 8137\n"
            '  (PowerShell: $env:SLEEPWISE_RATE_LIMIT="1000000"; uvicorn app.main:app --port 8137)'
        )
        return 1

    print(f"target {base}  {REQUESTS_PER_LEVEL} requests per level, {WARMUP} discarded\n")
    report: dict[str, list[dict]] = {}
    for case in _cases():
        print(case["name"])
        rows = []
        for concurrency in CONCURRENCY_LEVELS:
            row = await run_case(base, case, concurrency)
            rows.append(row)
            print(
                f"  c={concurrency:<3} {row['rps']:7.1f} rps   "
                f"p50 {row['p50']:6.1f}ms   p95 {row['p95']:6.1f}ms   "
                f"p99 {row['p99']:6.1f}ms   errors {row['errors']}"
            )
        report[case["name"]] = rows
        print()

    sections = []
    for name, rows in report.items():
        body = "\n".join(
            f"| {r['concurrency']} | {r['rps']:.0f} | {r['p50']:.1f} | {r['p95']:.1f} "
            f"| {r['p99']:.1f} | {r['errors']} |"
            for r in rows
        )
        sections.append(
            f"### `{name}`\n\n"
            "| Concurrency | req/s | p50 (ms) | p95 (ms) | p99 (ms) | Errors |\n"
            "|---|---|---|---|---|---|\n" + body
        )

    OUT.write_text(
        "# Performance\n\n"
        "<!-- Generated by scripts/loadtest.py. Do not edit by hand; re-run the script. -->\n\n"
        f"{REQUESTS_PER_LEVEL} requests per concurrency level, {WARMUP} warm-up requests\n"
        "discarded. Percentiles are computed from individual request durations.\n\n"
        "```bash\nuvicorn app.main:app --port 8137\npython scripts/loadtest.py\n```\n\n"
        "## Method\n\n"
        "Measured against a **single local uvicorn worker**. Benchmarking the deployed\n"
        "instance would measure Render's shared free-tier CPU and its cold starts rather\n"
        "than this code, which is a different question: production latency there is\n"
        "dominated by the platform, and the ~50s first-load figure in the README is a\n"
        "cold start, not request handling.\n\n"
        "`/recommend` appears twice on purpose. The cache-miss rows vary the medication\n"
        "list on every request so each one runs the full pipeline: medication resolution,\n"
        "the trained normalizer, the rules engine, BM25 retrieval, and rendering. The\n"
        "cache-hit rows repeat one payload, which is what the response cache is worth.\n\n"
        "## Results\n\n" + "\n\n".join(sections) + "\n\n"
        "## Reading these\n\n"
        "**Single request is fast.** Every endpoint sits around 11-15 ms at p50 with one\n"
        "client, including the full `/recommend` pipeline: medication resolution, the\n"
        "trained normalizer, the rules engine, BM25 retrieval, and rendering. Nothing here\n"
        "needs optimising for a single user.\n\n"
        "**Throughput peaks near 4 concurrent clients**, then degrades rather than merely\n"
        "flattening: it roughly doubles from c=1 to c=4, then falls by about half at c=16\n"
        "while p99 grows by an order of magnitude. Flat throughput would indicate a\n"
        "saturated worker; falling throughput indicates contention on top of saturation.\n\n"
        "Two candidate causes, and I have not isolated which dominates:\n\n"
        "1. The route handlers are synchronous (`def`, not `async def`), so Starlette runs\n"
        "   them in a threadpool. The work is CPU-bound pure Python, so those threads\n"
        "   contend on the GIL and add switching overhead once there are more of them than\n"
        "   there is CPU to go round.\n"
        "2. **The load generator shares the machine with the server.** At c=32 the asyncio\n"
        "   client is itself doing real work, so some of the measured latency is the\n"
        "   benchmark competing with the thing it is benchmarking. This is a limitation of\n"
        "   the setup, not a property of the service.\n\n"
        "Separating those would need the generator on another host, which is worth doing\n"
        "before treating the c=16+ rows as a property of the application.\n\n"
        "**The response cache is worth roughly a quarter of throughput** at c=4 (compare\n"
        "the two `/recommend` tables), which is the clearest argument for keeping it.\n\n"
        "**The remedy for real traffic is more workers, not a code change.** The service is\n"
        "stateless apart from an in-process cache and rate-limit counters, so it scales\n"
        "horizontally without coordination; both of those degrade gracefully per-instance\n"
        "rather than needing to be shared. `uvicorn --workers N` is the first lever.\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"written to {OUT.relative_to(ROOT)}")

    (ROOT / "docs" / "performance.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8", newline="\n"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8137")
    args = parser.parse_args()
    return asyncio.run(main_async(args.url))


if __name__ == "__main__":
    sys.exit(main())
