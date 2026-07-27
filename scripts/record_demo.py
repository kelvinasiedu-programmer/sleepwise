"""Regenerate the README demo GIF.

    python scripts/record_demo.py          # against a local server
    python scripts/record_demo.py --url https://sleepwise-90oh.onrender.com

Drives the real UI with Playwright, captures a frame per step, and stitches them into
`docs/demo.gif`. Scripted rather than screen-recorded so the demo can be regenerated
after a UI change instead of quietly going stale - a hand-recorded clip is a snapshot of
a version that no longer exists the moment the interface moves.

Requires: pip install -r requirements-bench.txt && playwright install chromium
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "demo.gif"

WIDTH, HEIGHT = 1000, 720
# Milliseconds each frame holds. Reading frames sit longer than transitions.
FRAME_MS = [2600, 3200, 3400, 3000, 2800]


def capture(url: str) -> list[bytes]:
    from playwright.sync_api import sync_playwright

    shots: list[bytes] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        page.goto(url, wait_until="networkidle")

        # 1. What it is: hero plus the scenario picker.
        page.wait_for_selector(".scenario-btn")
        shots.append(page.screenshot())

        # 2. Run the scenario that shows an option being withheld.
        page.get_by_role("button", name="Takes a benzodiazepine").click()
        page.wait_for_selector(".summary")
        page.evaluate("document.querySelector('.summary').scrollIntoView({block:'start'})")
        page.wait_for_timeout(400)
        shots.append(page.screenshot())

        # 3. The withheld item itself, with its reason.
        page.evaluate(
            "[...document.querySelectorAll('.card')]"
            ".find(c => c.textContent.includes('Valerian'))"
            "?.scrollIntoView({block:'center'})"
        )
        page.wait_for_timeout(400)
        shots.append(page.screenshot())

        # 4. Input the engine refuses to guess at.
        page.evaluate("window.scrollTo(0, 0)")
        page.get_by_role("button", name="Two medications in one entry").click()
        page.wait_for_selector(".notice")
        page.evaluate("document.querySelector('.notice').scrollIntoView({block:'center'})")
        page.wait_for_timeout(400)
        shots.append(page.screenshot())

        # 5. The second engine.
        page.goto(url.rstrip("/") + "/organizer", wait_until="networkidle")
        page.get_by_role("button", name="Start").click()
        page.wait_for_selector(".deck-card")
        page.wait_for_timeout(400)
        shots.append(page.screenshot())

        browser.close()
    return shots


def stitch(shots: list[bytes]) -> None:
    from PIL import Image

    frames = [Image.open(io.BytesIO(s)).convert("P", palette=Image.ADAPTIVE) for s in shots]
    durations = (FRAME_MS + [2500] * len(frames))[: len(frames)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8137")
    args = parser.parse_args()

    try:
        shots = capture(args.url)
    except Exception as exc:
        print(f"capture failed against {args.url}: {exc}")
        print("Is the server running?  uvicorn app.main:app --port 8137")
        return 1

    stitch(shots)
    size_kb = OUT.stat().st_size / 1024
    print(f"{len(shots)} frames -> {OUT.relative_to(ROOT)} ({size_kb:.0f} KB)")
    if size_kb > 5000:
        print("warning: over 5 MB; GitHub renders large GIFs slowly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
