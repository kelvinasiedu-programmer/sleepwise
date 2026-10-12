"""Verify that every cited source URL in the dataset is reachable.

Run:  python scripts/check_citations.py

Collects every unique source_url from data/*.json, requests each one, and fails
(exit 1) if any citation is unreachable. A broken citation means a claim is standing on
a link users cannot check, which this project treats as a data defect, not cosmetics.
Runs in CI weekly and whenever the data changes.

A host that refuses the checker itself (401/403/429) is reported as unverified, not
broken. NIH ODS put its fact sheets behind a Cloudflare bot check in August 2026 that
answers scripted clients with a 403 challenge page. The pages load fine in a browser, but
the check failed this job every week anyway.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HEADERS = {
    "User-Agent": "SleepWise-citation-check/1.0 (+https://github.com/kelvinasiedu-programmer/sleepwise)"
}
# The server answered, but refused this client. Says nothing about whether the page exists.
BLOCKED_STATUSES = frozenset({401, 403, 429})


def classify(status: int) -> str:
    """Map an HTTP status to ok, blocked (host refused the checker) or broken."""
    if status < 400:
        return "ok"
    if status in BLOCKED_STATUSES:
        return "blocked"
    return "broken"


def _rows(payload: object) -> list[dict]:
    """Every dict in a data file, whether it is a list or nested under object keys.

    The data directory holds both shapes: interaction_rules.json is a list, while
    symptom_topics.json nests lists under keys. Assuming a list silently crashed on the
    latter, which is how this checker was broken without anyone noticing.
    """
    if isinstance(payload, dict):
        out: list[dict] = []
        for value in payload.values():
            if isinstance(value, list):
                out.extend(item for item in value if isinstance(item, dict))
        return out
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def collect_urls() -> set[str]:
    urls: set[str] = set()
    for path in sorted(DATA_DIR.glob("*.json")):
        rows = _rows(json.loads(path.read_text(encoding="utf-8")))
        for row in rows:
            for key in ("source_url",):
                if row.get(key):
                    urls.add(row[key])
            for item in row.get("evidence", []) or []:
                if item.get("source_url"):
                    urls.add(item["source_url"])
    return urls


def main() -> int:
    urls = sorted(collect_urls())
    print(f"Checking {len(urls)} unique citation URLs...")
    failures: list[tuple[str, str]] = []
    blocked: list[str] = []
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0) as client:
        for url in urls:
            try:
                response = client.get(url)
                status = response.status_code
            except httpx.HTTPError as exc:
                failures.append((url, f"error: {exc.__class__.__name__}"))
                print(f"  FAIL {url} ({exc.__class__.__name__})")
                continue
            verdict = classify(status)
            if verdict == "broken":
                failures.append((url, f"HTTP {status}"))
                print(f"  FAIL {url} (HTTP {status})")
            elif verdict == "blocked":
                blocked.append(url)
                print(f"  WARN {url} (HTTP {status}, host refused the checker)")
                if in_actions:
                    print(
                        f"::warning title=Citation not verified::{url} returned HTTP "
                        f"{status} to the CI runner. Check it by hand in a browser."
                    )
            else:
                print(f"  ok   {url}")
    reachable = len(urls) - len(failures) - len(blocked)
    print(f"\n{reachable} reachable, {len(blocked)} unverified, {len(failures)} broken")
    if failures:
        print("Broken citations are data defects: fix the URL or quarantine the claim.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
