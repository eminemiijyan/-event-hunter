from src.append_miemu import parse_exhibitions, parse_prefecture_fallback

HTML = '''
<html><body>
<h1>企画展（2026年度）</h1>
<h2>企画展</h2>
<div>特別展・第42回企画展</div>
<h3>ポケモン化石博物館</h3>
<div>期間：2026年1月17日（土曜日）から2026年4月5日（日曜日）まで</div>
<div>第43回企画展</div>
<h3>まつりを旅する　受け継いできた三重の宝もの</h3>
<div>期間：2026年4月25日（土曜日）から2026年6月21日（日曜日）まで</div>
<div>第45回企画展</div>
<h3>みんなののりもの　三重の鉄道大集合</h3>
<div>期間：2026年10月24日（土曜日）から2027年2月28日（日曜日）まで</div>
<h2>三重の実物図鑑　特集展示</h2>
<h3>ミニ館蔵品展</h3>
<div>期間：2026年10月24日（土曜日）から2026年11月23日（月曜日・祝日）まで</div>
</body></html>
'''

events = parse_exhibitions(HTML)
assert len(events) == 3, events
assert events[0]["title"] == "ポケモン化石博物館"
assert events[2]["title"] == "みんなののりもの 三重の鉄道大集合"
assert events[2]["start_date"] == "2026-10-24"
assert events[2]["end_date"] == "2027-02-28"
assert events[2]["prefecture"] == "三重県"
assert events[2]["category"] == "展示会"
assert all("ミニ館蔵品展" not in e["title"] for e in events)

FALLBACK_HTML = '''
<html><body>
<h1>〖三重県総合博物館 MieMu〗第45回企画展　みんなののりもの　三重の鉄道大集合</h1>
<div>■期間</div>
<div>令和８年10月24日（土曜日）から令和９年2月28日（日曜日）まで</div>
<div>■場所</div><div>三重県総合博物館3階　企画展示室</div>
</body></html>
'''
fallback = parse_prefecture_fallback(FALLBACK_HTML)
assert len(fallback) == 1, fallback
assert fallback[0]["title"] == "みんなののりもの 三重の鉄道大集合"
assert fallback[0]["start_date"] == "2026-10-24"
assert fallback[0]["end_date"] == "2027-02-28"
assert fallback[0]["official_url"].startswith("https://www.pref.mie.lg.jp/")
print("PASS")
