from src.append_nagashima import discover_articles, parse_article, parse_date_span

LIST_HTML = '''
<html><body>
<a href="/spaland/info/vr.html">逃走中リミナルワールドVR空間で逃げ切れ in ナガシマスパーランド開催決定‼</a>
<a href="/spaland/info/pass.html">年間パスポート キャンペーン</a>
<a href="https://realdgame.jp/s/wizardpark/mie/">『夜の魔法学校からの脱出』</a>
<a href="/spaland/info/fishes.html">11/8（日）「フィッシャーズ」ステージイベント開催！</a>
</body></html>
'''
articles = discover_articles(LIST_HTML)
assert len(articles) == 2, articles
assert articles[0][1].endswith("/spaland/info/vr.html")
assert articles[1][1].endswith("/spaland/info/fishes.html")

VR_HTML = '''
<html><body>
<h1>逃走中リミナルワールドVR空間で逃げ切れ in ナガシマスパーランド開催決定‼</h1>
<div>2026年10月30日</div>
<div>開催日時</div><div>2026年12月12日（土）～2027年2月28日（日）</div>
<div>会場 ナガシマスパーランド内 ナガシマスパードーム</div>
</body></html>
'''
e = parse_article(VR_HTML, "https://www.nagashima-onsen.co.jp/spaland/info/vr.html")
assert e is not None
assert e["start_date"] == "2026-12-12"
assert e["end_date"] == "2027-02-28"
assert e["prefecture"] == "三重県"
assert e["source"] == "ナガシマスパーランド"

FISH_HTML = '''
<html><body>
<h1>11/8（日）「フィッシャーズ」ステージイベント開催！</h1>
<div>2026年10月26日</div>
<div>開催日時</div><div>2026年11月8日（日）</div>
</body></html>
'''
e = parse_article(FISH_HTML, "https://www.nagashima-onsen.co.jp/spaland/info/fishes.html")
assert e is not None
assert e["start_date"] == "2026-11-08"
assert e["end_date"] == "2026-11-08"
assert e["category"] == "コンサート・ショー"

HALLOWEEN_HTML = '''
<html><body>
<h1>NAGASHIMA HALLOWEEN ナガシマ ハロウィン2026</h1>
<div>2026年9月21日</div>
<div>ナガシマハロウィン | 開催期間：10/1（木）～11/3（火・祝）</div>
</body></html>
'''
e = parse_article(HALLOWEEN_HTML, "https://www.nagashima-onsen.co.jp/spaland/info/halloween.html")
assert e is not None
assert e["start_date"] == "2026-10-01"
assert e["end_date"] == "2026-11-03"
assert e["category"] == "祭り・季節"

start, end = parse_date_span("2026/11/14(土)〜2026/11/29(日)", 2026)
assert start.isoformat() == "2026-11-14"
assert end.isoformat() == "2026-11-29"
print("PASS")
