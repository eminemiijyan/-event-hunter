from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "site" / "events.json"
META_PATH = ROOT / "site" / "meta.json"
SNAPSHOT_PATH = ROOT / ".cache" / "previous_events.json"
REFERENCE_PATH = ROOT / "config" / "quality_reference.json"


def _event_is_current(event: dict, today: date) -> bool:
    raw = event.get("end_date") or event.get("start_date")
    if not raw:
        return False
    try:
        return date.fromisoformat(raw) >= today
    except (TypeError, ValueError):
        return False


def restore_missing_required_sources(
    current_events: list[dict],
    previous_events: list[dict],
    reference: dict,
    today: date,
) -> tuple[list[dict], dict[str, int]]:
    current_sources = {
        event.get("source")
        for event in current_events
        if event.get("source") and _event_is_current(event, today)
    }
    restored: dict[str, int] = {}
    result = list(current_events)

    for source, valid_until_raw in reference.get("required_sources", {}).items():
        try:
            valid_until = date.fromisoformat(valid_until_raw)
        except (TypeError, ValueError):
            continue
        if valid_until < today or source in current_sources:
            continue
        candidates = [
            event
            for event in previous_events
            if event.get("source") == source and _event_is_current(event, today)
        ]
        if not candidates:
            continue
        result.extend(candidates)
        restored[source] = len(candidates)
        current_sources.add(source)

    result.sort(key=lambda e: (e.get("start_date", ""), e.get("title", ""), e.get("source", "")))
    return result, restored


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    current_events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    if SNAPSHOT_PATH.exists():
        previous_events = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    else:
        previous_events = []

    events, restored = restore_missing_required_sources(current_events, previous_events, reference, today)
    if restored:
        EVENTS_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
        meta.update({
            "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
            "source_count": len({e.get("source") for e in events if e.get("source")}),
            "event_count": len(events),
            "decision_counts": counts,
            "restored_sources": restored,
        })
        META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        for source, count in restored.items():
            print("RESTORE_PREVIOUS", source, count, "events")
        print("RESTORE_PREVIOUS total", sum(restored.values()), "events")
    else:
        print("RESTORE_PREVIOUS none")


if __name__ == "__main__":
    main()
