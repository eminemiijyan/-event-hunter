from src.append_meiwa import parse_detail, parse_listing

LIST_HTML = '''
<html><body>
<h2><a href="/2026/10/31/tsuina/">第27回 追儺のまつりを開催します！</a></h2>
<h2><a href="/2026/10/20/fullmoon/">11月24日(火) 満月イベントのお知らせ</a></h2>
<h2><a href="/2026/09/10/kangetsu/">【プレスリリース】第23回いつきのみや観月会を開催！</a></h2>
</body></html>
'''
items = parse_listing(LIST_HTML)
assert [x["title"] for x in items] == [
    "第27回 追儺のまつりを開催します！",
    "第23回いつきのみや観月会を開催！",
]

DETAIL_HTML = '''
<html><body>
<h1>第27回 追儺のまつりを開催します！</h1>
<p>2026年10月31日 / 最終更新日時 : 2026年10月31日</p>
<p>開催日：2026年11月23日（月・祝）</p>
<p>会場：いつきのみや歴史体験館 周辺</p>
</body></html>
'''
item = parse_detail(DETAIL_HTML, "https://dmo.hana-meiwa.jp/2026/10/31/tsuina/")
assert item is not None
assert item["start_date"] == "2026-11-23"
assert item["end_date"] == "2026-11-23"
assert item["venue"].startswith("いつきのみや歴史体験館")
assert item["source"] == "明和観光商社"
print("PASS")
