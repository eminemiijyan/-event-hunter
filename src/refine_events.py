from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SITE_DIR = Path(__file__).resolve().parents[1] / "site"


def refine(events: list[dict]) -> list[dict]:
    for event in events:
        if event.get("source") != "名古屋コンシェルジュ":
            continue
        title = str(event.get("title") or "")
        if "マルシェ" in title and event.get("decision") == "display":
            event["decision"] = "hold"
            event["decision_reason"] = "マルシェは規模不明のため保留"
    return events


def main():
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    events = refine(events)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in events),
        "hold": sum(e.get("decision") == "hold" for e in events),
        "exclude": sum(e.get("decision") == "exclude" for e in events),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("REFINE", counts)


if __name__ == "__main__":
    main()
