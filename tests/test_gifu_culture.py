from src.append_gifu_culture import append_events, category_for, parse_events

SAMPLE = '''
<html><body>
<h2>2026年11月イベント案内</h2>
<table>
<tr><th>日時・会場</th><th>催し物名</th><th>料金</th></tr>
<tr><td>21日（土） 09:30～16:00 催し広場</td><td>みらいワクワク！こども仕事体験フェスタin岐阜</td><td>無料</td></tr>
<tr><td>28日・29日（土）・（日） 12:00～20:30 催し広場</td><td>MASTERPIECE 2026</td><td>有料</td></tr>
</table>
</body></html>
'''

events = parse_events(SAMPLE)
assert len(events) == 2
assert events[0]["start_date"] == "2026-11-21"
assert events[0]["end_date"] == "2026-11-21"
assert events[0]["venue"] == "岐阜市文化センター 催し広場"
assert events[0]["decision"] == "display"
assert events[1]["start_date"] == "2026-11-28"
assert events[1]["end_date"] == "2026-11-29"
assert events[1]["category"] == "コンサート・ショー"
assert category_for("第44回 ぎふ市民健康まつり") == "祭り・季節"

existing = [{
    "title": "MASTERPIECE 2026",
    "start_date": "2026-11-28",
    "end_date": "2026-11-29",
}]
assert len(append_events(existing, [events[1]])) == 1
print("PASS")
