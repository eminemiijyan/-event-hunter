from datetime import date

from src.normalize_categories import DISPLAY_CATEGORIES, normalize
from src.restore_previous_sources import restore_missing_required_sources

reference = {
    "required_sources": {
        "source-a": "2026-11-30",
        "source-b": "2026-12-31",
        "expired-source": "2026-10-01",
    },
    "warn_sources": {
        "warn-source": "2027-02-28",
    },
}

today = date(2026, 10, 31)
current = [
    {"source": "source-a", "title": "A", "start_date": "2026-11-01", "end_date": "2026-11-02"},
]
previous = [
    {"source": "source-a", "title": "old A", "start_date": "2026-11-03", "end_date": "2026-11-04"},
    {"source": "source-b", "title": "B1", "start_date": "2026-11-10", "end_date": "2026-11-10"},
    {"source": "source-b", "title": "B2", "start_date": "2026-12-01", "end_date": "2026-12-02"},
    {"source": "source-b", "title": "old B", "start_date": "2026-09-01", "end_date": "2026-09-02"},
    {"source": "warn-source", "title": "W1", "start_date": "2027-01-10", "end_date": "2027-01-10"},
    {"source": "expired-source", "title": "expired", "start_date": "2026-11-01", "end_date": "2026-11-01"},
]

restored_events, restored = restore_missing_required_sources(current, previous, reference, today)
assert restored == {"source-b": 2, "warn-source": 1}
assert [e["title"] for e in restored_events if e["source"] == "source-a"] == ["A"]
assert {e["title"] for e in restored_events if e["source"] == "source-b"} == {"B1", "B2"}
assert [e["title"] for e in restored_events if e["source"] == "warn-source"] == ["W1"]
assert not any(e["source"] == "expired-source" for e in restored_events)

already_current = current + [
    {"source": "source-b", "title": "fresh B", "start_date": "2026-11-20", "end_date": "2026-11-20"},
    {"source": "warn-source", "title": "fresh W", "start_date": "2027-01-20", "end_date": "2027-01-20"},
]
restored_events, restored = restore_missing_required_sources(already_current, previous, reference, today)
assert restored == {}
assert [e["title"] for e in restored_events if e["source"] == "source-b"] == ["fresh B"]
assert [e["title"] for e in restored_events if e["source"] == "warn-source"] == ["fresh W"]

no_snapshot_events, restored = restore_missing_required_sources(current, [], reference, today)
assert restored == {}
assert no_snapshot_events == current

category_events = [
    {"title": "パンマルシェ", "category": "グルメ", "source": "x", "venue": "x"},
    {"title": "コミックフロンティア", "category": "展示会・イベント", "source": "アクトシティ浜松", "venue": "x"},
    {"title": "オペラコンクール", "category": "展示会・イベント", "source": "アクトシティ浜松", "venue": "x"},
    {"title": "デジタルスタンプラリー", "category": "その他", "source": "x", "venue": "x"},
]
normalize(category_events)
assert category_events[0]["category"] == "グルメ・マーケット"
assert category_events[1]["category"] == "ゲーム・アニメ"
assert category_events[2]["category"] == "音楽・舞台"
assert category_events[3]["category"] == "体験・ファミリー"
assert category_events[0]["source_category"] == "グルメ"
assert all(e["category"] in DISPLAY_CATEGORIES for e in category_events)
normalize(category_events)
assert category_events[0]["source_category"] == "グルメ"

print("PASS")
