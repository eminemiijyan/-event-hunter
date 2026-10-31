from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "site" / "events.json"
META_PATH = ROOT / "site" / "meta.json"
REFERENCE_PATH = ROOT / "config" / "quality_reference.json"

REQUIRED_EVENT_FIELDS = (
    "title",
    "start_date",
    "end_date",
    "venue",
    "prefecture",
    "category",
    "source",
    "official_url",
    "decision",
)
VALID_DECISIONS = {"display", "hold", "exclude"}


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


def event_integrity_errors(events: list[dict]) -> list[str]:
    errors: list[str] = []
    for index, event in enumerate(events):
        label = str(event.get("title") or f"#{index + 1}")
        missing = [field for field in REQUIRED_EVENT_FIELDS if not str(event.get(field) or "").strip()]
        if missing:
            errors.append(f"{label}: 必須項目欠落 {','.join(missing)}")
            continue

        try:
            start = date.fromisoformat(str(event["start_date"]))
            end = date.fromisoformat(str(event["end_date"]))
        except (TypeError, ValueError):
            errors.append(f"{label}: 日付形式不正 {event.get('start_date')}〜{event.get('end_date')}")
            continue

        if end < start:
            errors.append(f"{label}: 終了日が開始日より前 {start.isoformat()}〜{end.isoformat()}")
        if event.get("decision") not in VALID_DECISIONS:
            errors.append(f"{label}: decision不正 {event.get('decision')}")
        if not str(event.get("official_url") or "").startswith(("https://", "http://")):
            errors.append(f"{label}: 公式URL不正 {event.get('official_url')}")

    return sorted(set(errors))


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def duplicate_warnings(events: list[dict]) -> list[str]:
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for event in events:
        key = (
            _norm(event.get("title")),
            str(event.get("start_date") or ""),
            _norm(event.get("venue")),
            str(event.get("prefecture") or ""),
        )
        if not key[0] or not key[1] or not key[2]:
            continue
        groups.setdefault(key, []).append(event)

    warnings: list[str] = []
    for items in groups.values():
        if len(items) < 2:
            continue
        sources = sorted({str(item.get("source") or "不明") for item in items})
        title = str(items[0].get("title") or "")
        warnings.append(f"重複候補: {title} / {items[0].get('start_date')} / 情報源 {'・'.join(sources)}")
    return sorted(set(warnings))


def restored_source_warnings(meta: dict) -> list[str]:
    restored = meta.get("restored_sources")
    if not isinstance(restored, dict):
        return []
    warnings = []
    for source, count in sorted(restored.items()):
        warnings.append(f"{source}: 今回取得失敗のため前回データ {count}件を復元")
    return warnings


def degraded_source_warnings(meta: dict) -> list[str]:
    degraded = meta.get("degraded_sources")
    if not isinstance(degraded, dict):
        return []
    warnings = []
    for source, reason in sorted(degraded.items()):
        text = str(reason or "一部取得に失敗")
        warnings.append(f"{source}: {text}")
    return warnings


def _write_quality_warnings(meta: dict, warnings: list[str]) -> None:
    meta["quality_warnings"] = warnings
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    integrity_errors = event_integrity_errors(events)
    missing = missing_required_sources(events, reference, today)
    warnings = sorted(set(
        coverage_warnings(events, reference, today)
        + restored_source_warnings(meta)
        + degraded_source_warnings(meta)
        + duplicate_warnings(events)
    ))
    _write_quality_warnings(meta, warnings)

    if integrity_errors:
        print("QUALITY_GATE FAIL event integrity:")
        for error in integrity_errors:
            print(" -", error)
        raise SystemExit(1)

    if missing:
        print("QUALITY_GATE FAIL missing required sources:")
        for source in missing:
            print(" -", source)
        raise SystemExit(1)

    if warnings:
        print("QUALITY_GATE WARN coverage/source/data issues:")
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
