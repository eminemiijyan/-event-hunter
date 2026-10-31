from src.append_hamamatsu_kanko import discover_month_articles, parse_month_article

archive = '''
<html><body>
<a href="/information/7249/">2026年11月イベント情報</a>
<a href="/information/7000/">10月イベント情報</a>
</body></html>
'''
articles = discover_month_articles(archive)
assert articles == [("https://hamamatsu-daisuki.net/information/7249/", 2026, 11)]

page = '''
<html><body>
<h2>🌷はままつフラワーパーク</h2>
<h3>浜松菊花大会</h3><p>11月2日～11月23日</p>
<h2>🌙浜松科学館 みらい～ら</h2>
<h3>プラネタリウム「星空マルシェ」</h3><p>11月1日～12月25日</p>
<h2>2026はまきた産業祭</h2><p>11月7日～11月8日 10:00～16:00</p><p>📍サンストリート浜北</p>
<h3>木のスプーン作り教室</h3><p>11月23日</p>
<h2>はままつインターカルチュラルシティフェスティバル2026</h2><p>11月29日 10:00～18:00</p><p>📍ソラモ</p>
</body></html>
'''
items = parse_month_article(page, 2026, 11, "https://hamamatsu-daisuki.net/information/7249/")
assert [x["title"] for x in items] == ["浜松菊花大会", "2026はまきた産業祭", "はままつインターカルチュラルシティフェスティバル2026"]
assert items[0]["start_date"] == "2026-11-02"
assert items[0]["end_date"] == "2026-11-23"
assert items[1]["start_date"] == "2026-11-07"
assert items[1]["end_date"] == "2026-11-08"
assert items[1]["venue"] == "サンストリート浜北"
assert items[2]["start_date"] == "2026-11-29"
assert items[2]["venue"] == "ソラモ"
assert all("プラネタリウム" not in x["title"] for x in items)
print("PASS")
