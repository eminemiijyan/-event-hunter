from src.append_watarai import parse_detail, parse_listing

LIST_HTML = '''
<html><body>
<a href="/contents_detail.php?frmId=3790">「バイクフリーミーティングin宮リバー度会パークvol.12」開催のお知らせ</a>
<a href="/contents_detail.php?frmId=3798">宮リバー度会パークイルミネーションプロジェクト2026開催のお知らせ</a>
<a href="/contents_detail.php?frmId=1000">わたらいセブンマウンテンマップ</a>
<a href="/contents_detail.php?frmId=1001">わたらい茶会 2026 in三重テラス</a>
</body></html>
'''

items = parse_listing(LIST_HTML)
assert [x["title"] for x in items] == [
    "「バイクフリーミーティングin宮リバー度会パークvol.12」開催のお知らせ",
    "宮リバー度会パークイルミネーションプロジェクト2026開催のお知らせ",
]

BIKE_HTML = '''
<html><body>
<h1>「バイクフリーミーティングin宮リバー度会パークvol.12」開催のお知らせ</h1>
<p>[2026年10月22日]</p>
<h3>日時</h3><p>令和8年11月8日(日) 午前9時から午後3時まで</p>
<h3>場所</h3><p>宮リバー度会パーク 芝生広場内</p>
</body></html>
'''
item = parse_detail(BIKE_HTML, "https://example.test/bike")
assert item is not None
assert item["start_date"] == "2026-11-08"
assert item["end_date"] == "2026-11-08"
assert "宮リバー度会パーク" in item["venue"]

LIGHT_HTML = '''
<html><body>
<h1>宮リバー度会パークイルミネーションプロジェクト2026開催のお知らせ</h1>
<p>[2026年10月16日]</p>
<h3>開催日</h3>
<p>11月14日(土) 17:00から20:00まで</p>
<p>11月15日(日) 18:00から20:00まで</p>
</body></html>
'''
item = parse_detail(LIGHT_HTML, "https://example.test/light")
assert item is not None
assert item["start_date"] == "2026-11-14"
assert item["end_date"] == "2026-11-15"
assert item["category"] == "祭り・季節"
print("PASS")
