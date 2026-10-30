from src.append_minamiise import parse_detail, parse_listing

LIST_HTML = '''
<html><body>
<a href="/event_osakana2026.html">南伊勢おさかなフェスタ2026開催！</a>
<a href="/event_stamp2026.html">南伊勢町スタンプラリー</a>
<a href="/event_photo.html">フォトコンテスト開催</a>
</body></html>
'''
items = parse_listing(LIST_HTML)
assert [x["title"] for x in items] == ["南伊勢おさかなフェスタ2026開催！"]

DETAIL_HTML = '''
<html><body>
<h1>南伊勢おさかなフェスタ2026開催！</h1>
<p>開催日：2026年11月22日</p>
<h3>会場</h3><p>奈屋浦漁港</p>
</body></html>
'''
item = parse_detail(DETAIL_HTML, "https://www.minami-ise.jp/event_osakana2026.html")
assert item is not None
assert item["start_date"] == "2026-11-22"
assert item["end_date"] == "2026-11-22"
assert item["venue"] == "奈屋浦漁港"
assert item["source"] == "南伊勢町観光協会"

NO_DATE = '''<html><body><h1>11月 おさかなフェスタ</h1><p>秋に開催予定です。</p></body></html>'''
assert parse_detail(NO_DATE, "https://www.minami-ise.jp/no-date.html") is None
print("PASS")
