from src.append_toba_aquarium import parse_active_events

HTML = '''
<html><body>
<h2>イベント情報</h2>
<a href="/event/summer2027/">2027年7月17日（土）～2027年9月20日（月） 夏の企画展「海のふしぎ大冒険」</a>
<a href="/event/tour2027/">2027年6月1日（火）～2027年12月1日（水） 2027特別バックヤードツアー 開催中</a>
<h3>終了したイベント</h3>
<a href="/event/xmas2026/">2026年11月29日（日）～2026年12月25日（金） トバスイ☆クリスマス2026</a>
</body></html>
'''

events = parse_active_events(HTML)
assert len(events) == 1, events
assert events[0]["title"] == "夏の企画展「海のふしぎ大冒険」"
assert events[0]["start_date"] == "2027-07-17"
assert events[0]["end_date"] == "2027-09-20"
assert events[0]["venue"] == "鳥羽水族館"
assert events[0]["source"] == "鳥羽水族館"
assert "バックヤード" not in events[0]["title"]
print("PASS")
