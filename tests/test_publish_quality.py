from datetime import date

from src.validate_publish import coverage_warnings, missing_required_sources

reference = {
    "required_sources": {
        "source-a": "2026-11-30",
        "source-b": "2026-12-31",
        "expired-source": "2026-10-01",
    },
    "warn_sources": {
        "source-c": "2027-02-28",
    },
}

events = [
    {"source": "source-a", "start_date": "2026-11-01", "end_date": "2026-11-02"},
    {"source": "expired-source", "start_date": "2026-09-01", "end_date": "2026-09-02"},
]

today = date(2026, 10, 31)
assert missing_required_sources(events, reference, today) == ["source-b"]

warnings = coverage_warnings(events, reference, today)
assert "source-a: 最新取得日 2026-11-02 / 基準 2026-11-30" in warnings
assert "source-c: 取得できていません / 基準 2027-02-28" in warnings

events.append({"source": "source-b", "start_date": "2026-12-01", "end_date": "2026-12-31"})
assert missing_required_sources(events, reference, today) == []

events.append({"source": "source-a", "start_date": "2026-11-30", "end_date": "2026-11-30"})
events.append({"source": "source-c", "start_date": "2027-02-28", "end_date": "2027-02-28"})
assert coverage_warnings(events, reference, today) == []

print("PASS")
