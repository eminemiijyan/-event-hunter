from __future__ import annotations

import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".cache"
SNAPSHOT_PATH = CACHE_DIR / "previous_events.json"
PUBLISHED_EVENTS_URL = "https://eminemiijyan.github.io/-event-hunter/events.json"


def fetch_previous_events(url: str = PUBLISHED_EVENTS_URL) -> list[dict]:
    response = requests.get(
        url,
        timeout=(10, 45),
        headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)"},
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError("published events payload must be a list")
    return [item for item in data if isinstance(item, dict)]


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        events = fetch_previous_events()
    except (requests.RequestException, ValueError) as exc:
        print("PREVIOUS_SNAPSHOT unavailable", type(exc).__name__)
        SNAPSHOT_PATH.write_text("[]\n", encoding="utf-8")
        return
    SNAPSHOT_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    sources = len({e.get("source") for e in events if e.get("source")})
    print("PREVIOUS_SNAPSHOT saved", len(events), "events", sources, "sources")


if __name__ == "__main__":
    main()
