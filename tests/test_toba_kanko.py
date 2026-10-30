from src.append_toba_kanko import parse_listing

HTML = '''
<html><body>
<div><span>2026年</span><span>10/10</span><a href="/events/5466/">第25回鳥羽クラフト展とプレイフルマルシェ エリア鳥羽 開催日2026年10月10日（土）～11日（日） 時間10:00 場所鳥羽市民の森公園 問い合わせ鳥羽市観光協会</a></div>
<div><span>2026年</span><span>10/31</span><a href="/events/5768/">第三回・伊勢西国三十三所巡礼（ウォーキング）体験 エリア二見 時間10:30 場所三重県伊勢市二見町 問い合わせ太江寺</a></div>
<div><a href="/events/5870/">伊射波神社例大祭・御魚取り（ミトトリ）神事 エリア安楽島町 時間10時 場所伊射波神社 問い合わせ中村宮司</a><span>11/23</span></div>
<div><a href="/events/5867/">二船祭 エリア国崎町 場所祭典（神事）：海士潜女神社 問い合わせ国崎町内会</a><span>11/23</span></div>
</body></html>
'''

events = parse_listing(HTML, default_year=2026)
assert len(events) == 3, events
assert events[0]["title"] == "第25回鳥羽クラフト展とプレイフルマルシェ"
assert events[0]["start_date"] == "2026-10-10"
assert events[0]["end_date"] == "2026-10-11"
assert events[0]["venue"] == "鳥羽市民の森公園"
assert events[1]["title"].startswith("伊射波神社例大祭")
assert events[1]["start_date"] == "2026-11-23"
assert events[1]["venue"] == "伊射波神社"
assert events[2]["title"] == "二船祭"
assert events[2]["start_date"] == "2026-11-23"
assert all(e["source"] == "鳥羽市観光協会" for e in events)
assert all("巡礼" not in e["title"] for e in events)
print("PASS")
