from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "site" / "events.json"
META_PATH = ROOT / "site" / "meta.json"
REFERENCE_PATH = ROOT / "config" / "quality_reference.json"


def _parse_event_end(event: dict) -> date | None:
    raw = event.get("end_date") or event.get("start_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _event_is_current(event: dict, today: date) -> bool:
    event_end = _parse_event_end(event)
    return event_end is not None and event_end >= today


def _source_max_end_dates(events: list[dict], today: date) -> dict[str, date]:
    latest: dict[str, date] = {}
    for event in events:
        source = event.get("source")
        event_end = _parse_event_end(event)
        if not source or event_end is None or event_end < today:
            continue
        if source not in latest or event_end > latest[source]:
            latest[source] = event_end
    return latest


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


def coverage_warnings(events: list[dict], reference: dict, today: date) -> list[str]:
    latest = _source_max_end_dates(events, today)
    warnings: list[str] = []

    for source, valid_until_raw in reference.get("required_sources", {}).items():
        valid_until = date.fromisoformat(valid_until_raw)
        if valid_until < today or source not in latest:
            continue
        if latest[source] < valid_until:
            warnings.append(
                f"{source}: 最新取得日 {latest[source].isoformat()} / 基準 {valid_until.isoformat()}"
            )

    for source, valid_until_raw in reference.get("warn_sources", {}).items():
        valid_until = date.fromisoformat(valid_until_raw)
        if valid_until < today:
            continue
        actual = latest.get(source)
        if actual is None:
            warnings.append(
                f"{source}: 取得できていません / 基準 {valid_until.isoformat()}"
            )
        elif actual < valid_until:
            warnings.append(
                f"{source}: 最新取得日 {actual.isoformat()} / 基準 {valid_until.isoformat()}"
            )

    return sorted(set(warnings))


def _write_quality_warnings(warnings: list[str]) -> None:
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    meta["quality_warnings"] = warnings
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    missing = missing_required_sources(events, reference, today)
    warnings = coverage_warnings(events, reference, today)
    _write_quality_warnings(warnings)

    if missing:
        print("QUALITY_GATE FAIL missing required sources:")
        for source in missing:
            print(" -", source)
        raise SystemExit(1)

    if warnings:
        print("QUALITY_GATE WARN coverage/source issues:")
        for warning in warnings:
            print(" -", warning)

    required_now = sum(
        date.fromisoformat(v) >= today
        for v in reference.get("required_sources", {}).values()
    )
    print(
        "QUALITY_GATE PASS",
        "required_sources",
        required_now,
        "events",
        len(events),
        "warnings",
        len(warnings),
    )


if __name__ == "__main__":
    main()
