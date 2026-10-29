from src.append_aichi_now import append_pickups, category_for, parse_detail, parse_dates, pickup_links

LIST_SAMPLE = '''
<html><body>
<h2>ピックアップイベント</h2>
<ul>
<li><a href="/events/detail/4171/">半田発酵日和 2026年10月31日(土)、11月1日(日)</a></li>
<li><a href="/events/detail/131/">第71回 香嵐渓もみじまつり 2026年11月1日(日) ～ 11月30日(月)</a></li>
</ul>
<form></form>
<a href="/events/detail/9999/">通常検索結果</a>
</body></html>
'''
links = pickup_links(LIST_SAMPLE)
assert links == [
    "https://aichinow.pref.aichi.jp/events/detail/4171/",
    "https://aichinow.pref.aichi.jp/events/detail/131/",
]

DETAIL_SAMPLE = '''
<html><body>
<h2>半田発酵日和</h2>
<table>
<tr><th>開催日</th><td>2026年10月31日(土)、11月1日(日)</td></tr>
<tr><th>開催時間</th><td>10:00～16:00</td></tr>
<tr><th>開催場所</th><td>半田赤レンガ建物</td></tr>
<tr><th>所在地</th><td>半田市榎下町8</td></tr>
</table>
</body></html>
'''
e = parse_detail(DETAIL_SAMPLE, "https://aichinow.pref.aichi.jp/events/detail/4171/")
assert e is not None
assert e["title"] == "半田発酵日和"
assert e["start_date"] == "2026-10-31"
assert e["end_date"] == "2026-11-01"
assert e["venue"] == "半田赤レンガ建物"
assert e["category"] == "グルメ"
assert e["decision"] == "display"

assert parse_dates("2026年11月1日(日) ～ 11月30日(月)") == ("2026-11-01", "2026-11-30")
assert category_for("第71回 香嵐渓もみじまつり") == "祭り・季節"

existing = [{
    "title": "半田 発酵日和",
    "start_date": "2026-10-31",
    "end_date": "2026-11-01",
    "venue": "別表記",
}]
merged = append_pickups(existing, [e])
assert len(merged) == 1
print("PASS")
