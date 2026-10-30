from src.append_mie_art import parse_prefecture_listing, parse_primary

PRIMARY = '''
<html><body>
<h2>2026年度の企画展</h2>
<h3>三重県誕生150周年記念 生誕100周年 榊莫山</h3>
<p>2026年4月4日（土）－5月31日（日）</p>
<p>一般：800円</p>
<h3>ルーシー・リー展―東西をつなぐ優美のうつわ―</h3>
<p>2026年9月26日（土）－12月13日（日）</p>
<p>一般：1,200円</p>
<h2>新収蔵品展</h2>
<h3>新収蔵品展 久保舎己</h3>
<p>2026年12月1日（火）－12月27日（日）</p>
</body></html>
'''

FALLBACK = '''
<html><body>
<div>2026/09/19-2026/11/15</div>
<div>〖斎宮歴史博物館〗特別展「大斎院」</div>
<div>2026/09/26-2026/12/13</div>
<div>〖三重県立美術館〗企画展「ルーシー・リー展 ―東西をつなぐ優美のうつわ―」</div>
<div>2026/10/01-2026/12/27</div>
<div>〖三重県総合文化センター〗窓アート</div>
</body></html>
'''

primary = parse_primary(PRIMARY)
assert len(primary) == 2, primary
assert primary[0]["start_date"] == "2026-04-04"
assert primary[0]["end_date"] == "2026-05-31"
assert primary[1]["title"].startswith("ルーシー・リー展")
assert primary[1]["start_date"] == "2026-09-26"
assert primary[1]["end_date"] == "2026-12-13"
assert all(e["source"] == "三重県立美術館" for e in primary)
assert all("新収蔵品展" not in e["title"] for e in primary)

fallback = parse_prefecture_listing(FALLBACK, "https://www.pref.mie.lg.jp/app/events/search/0/2")
assert len(fallback) == 1, fallback
assert fallback[0]["title"] == "ルーシー・リー展 ―東西をつなぐ優美のうつわ―"
assert fallback[0]["start_date"] == "2026-09-26"
assert fallback[0]["end_date"] == "2026-12-13"
assert fallback[0]["venue"] == "三重県立美術館"
print("PASS")
