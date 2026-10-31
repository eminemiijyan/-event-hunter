from datetime import date

from src.validate_publish import (
    coverage_warnings,
    degraded_source_warnings,
    duplicate_warnings,
    event_integrity_errors,
    missing_required_sources,
    restored_source_warnings,
    source_count_drop_warnings,
)

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

valid = {
    "title": "大型イベント",
    "start_date": "2026-11-01",
    "end_date": "2026-11-03",
    "venue": "会場A",
    "prefecture": "愛知県",
    "category": "展示会",
    "source": "公式A",
    "official_url": "https://example.test/event-a",
    "decision": "display",
}
assert event_integrity_errors([valid]) == []

bad_date = dict(valid, title="日付逆転", start_date="2026-11-03", end_date="2026-11-01")
assert event_integrity_errors([bad_date]) == ["日付逆転: 終了日が開始日より前 2026-11-03〜2026-11-01"]

missing_venue = dict(valid, title="会場なし", venue="")
assert event_integrity_errors([missing_venue]) == ["会場なし: 必須項目欠落 venue"]

bad_decision = dict(valid, title="判定不正", decision="maybe")
assert event_integrity_errors([bad_decision]) == ["判定不正: decision不正 maybe"]

other_source = dict(valid, source="公式B", official_url="https://example.test/event-b")
dupes = duplicate_warnings([valid, other_source])
assert dupes == ["重複候補: 大型イベント / 2026-11-01 / 情報源 公式A・公式B"]

assert restored_source_warnings({"restored_sources": {"モリコロパーク": 5}}) == [
    "モリコロパーク: 今回取得失敗のため前回データ 5件を復元"
]
assert restored_source_warnings({}) == []

assert degraded_source_warnings({"degraded_sources": {"伊勢市観光協会": "詳細ページ 1/4件取得失敗"}}) == [
    "伊勢市観光協会: 詳細ページ 1/4件取得失敗"
]
assert degraded_source_warnings({}) == []

previous = [dict(valid, title=f"E{i}", source="公式X") for i in range(6)]
current = [dict(valid, title=f"E{i}", source="公式X") for i in range(2)]
assert source_count_drop_warnings(current, previous, today) == ["公式X: 件数急減 前回6件→今回2件"]
assert source_count_drop_warnings(previous[:4], previous[:4], today) == []
assert source_count_drop_warnings(previous[:3], previous, today) == []

print("PASS")
