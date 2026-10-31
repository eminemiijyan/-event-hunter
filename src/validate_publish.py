from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "site" / "events.json"
REFERENCE_PATH = ROOT / "config" / "quality_reference.json"


def _event_is_current(event: dict, today: date) -> bool:
    raw = event.get("end_date") or event.get("start_date")
    if not raw:
        return False
    try:
        return date.fromisoformat(raw) >= today
    except ValueError:
        return False


def missing_required_sources(events: list[dict], reference: dict, today: date) -> list[str]:
    current_sources = {
        e.get("source")
        for e in events
        if e.get("source") and _event_is_current(e, today)
    }
    missing: list[str] = []
    for source, valid_until_raw in reference.get("required_sources", {}).items():
        try:
            valid_until = date.fromisoformat(valid_until_raw)
        except ValueError:
            raise ValueError(f"invalid quality-reference date for {source}: {valid_until_raw}")
        if valid_until >= today and source not in current_sources:
            missing.append(source)
    return sorted(missing)


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    missing = missing_required_sources(events, reference, today)
    if missing:
        print("QUALITY_GATE FAIL missing required sources:")
        for source in missing:
            print(" -", source)
        raise SystemExit(1)
    required_now = sum(
        date.fromisoformat(v) >= today
        for v in reference.get("required_sources", {}).values()
    )
    print("QUALITY_GATE PASS", "required_sources", required_now, "events", len(events))


if __name__ == "__main__":
    main()
