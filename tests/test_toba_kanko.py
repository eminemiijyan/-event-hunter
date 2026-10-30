from src.append_toba_kanko import parse_listing

HTML = '''
<html><body>
<div><span>2026年</span><span>10/10</span><a href="/events/5466/">第25回鳥羽クラフト展とプレイフルマルシェ エリア鳥羽 開催日2026年10月10日（土）～11日（日） 時間10:00 場所鳥羽市民の森公園 問い合わせ鳥羽市観光協会</a></div>
<div><span>2026年</span><span>10/31</span><a href="/events/5768/">第三回・伊勢西国三十三所巡礼（ウォーキング）体験 エリア二見 時間10:30 場所三重県伊勢市二見町 問い合わせ太江寺</a></div>
<div><a href="/events/5870/">伊射波神社例大祭・御魚取り（ミトトリ）神事 エリア安楽島町 時間10時 場所伊射波神社 問い合わせ中村宮司</a><span>１１／</span><strong>２３</strong></div>
<div><a href="/events/5867/">二船祭 エリア国崎町 場所祭典（神事）：海士潜女神社 問い合わせ国崎町内会</a><span>11/</span><strong>23</strong></div>
</body></html>
'''

events = parse_listing(HTML, default_year=2026)
assert len(events) == 3, events
by_title = {e["title"]: e for e in events}

craft = by_title["第25回鳥羽クラフト展とプレイフルマルシェ"]
assert craft["start_date"] == "2026-10-10"
assert craft["end_date"] == "2026-10-11"
assert craft["venue"] == "鳥羽市民の森公園"

isawa = next(e for e in events if e["title"].startswith("伊射波神社例大祭"))
assert isawa["start_date"] == "2026-11-23"
assert isawa["venue"] == "伊射波神社"

futafune = by_title["二船祭"]
assert futafune["start_date"] == "2026-11-23"

assert all(e["source"] == "鳥羽市観光協会" for e in events)
assert all("巡礼" not in e["title"] for e in events)
print("PASS")
