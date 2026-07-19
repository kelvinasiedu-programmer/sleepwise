"""Verify that every cited source URL in the dataset is reachable.

Run:  python scripts/check_citations.py

Collects every unique source_url from data/*.json, requests each one, and fails
(exit 1) if any citation is unreachable. A broken citation means a claim is standing on
a link users cannot check, which this project treats as a data defect, not cosmetics.
Runs in CI weekly and whenever the data changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HEADERS = {
    "User-Agent": "SleepWise-citation-check/1.0 (+https://github.com/kelvinasiedu-programmer/sleepwise)"
}


def collect_urls() -> set[str]:
    urls: set[str] = set()
    for path in sorted(DATA_DIR.glob("*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
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
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20.0) as client:
        for url in urls:
            try:
                response = client.get(url)
                status = response.status_code
            except httpx.HTTPError as exc:
                failures.append((url, f"error: {exc.__class__.__name__}"))
                print(f"  FAIL {url} ({exc.__class__.__name__})")
                continue
            if status >= 400:
                failures.append((url, f"HTTP {status}"))
                print(f"  FAIL {url} (HTTP {status})")
            else:
                print(f"  ok   {url}")
    print(f"\n{len(urls) - len(failures)} reachable, {len(failures)} broken")
    if failures:
        print("Broken citations are data defects: fix the URL or quarantine the claim.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
