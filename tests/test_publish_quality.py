from datetime import date

from src.validate_publish import missing_required_sources

reference = {
    "required_sources": {
        "source-a": "2026-11-30",
        "source-b": "2026-12-31",
        "expired-source": "2026-10-01",
    }
}

events = [
    {"source": "source-a", "start_date": "2026-11-01", "end_date": "2026-11-02"},
    {"source": "expired-source", "start_date": "2026-09-01", "end_date": "2026-09-02"},
]

assert missing_required_sources(events, reference, date(2026, 10, 31)) == ["source-b"]

events.append({"source": "source-b", "start_date": "2026-12-01", "end_date": "2026-12-01"})
assert missing_required_sources(events, reference, date(2026, 10, 31)) == []

print("PASS")
