from datetime import date
from src.append_niterra import discover_month_pages, parse_month

HOME = """
<html><body>
<a href="/kaikan/event/847.html">2026年10月</a>
<a href="/kaikan/event/848.html">2026年11月</a>
<a href="/kaikan/event/700.html">2026年9月</a>
</body></html>
"""
pages = discover_month_pages(HOME, date(2026, 10, 30))
assert [(y, m) for y, m, _ in pages] == [(2026, 10), (2026, 11)]

PAGE = """
<html><body>
<h1>2026年11月</h1>
<h2>フォレストホール(大ホール)</h2>
<table>
<tr><th>開催日</th><th>催物名称</th><th>問合せ</th><th>時間</th><th>料金</th></tr>
<tr><td>3日(火祝)</td><td>佐野元春 &amp; THE COYOTE BAND</td><td>主催</td><td>18:00</td><td>12,100円</td></tr>
<tr><td>5日(木)</td><td>第48回名古屋市保健環境委員大会</td><td>主催</td><td>14:00</td><td>関係者 のみ</td></tr>
<tr><td>24日(火)</td><td rowspan="2">さだまさしコンサートツアー2026</td><td rowspan="2">主催</td><td>18:00</td><td rowspan="2">11,000円</td></tr>
<tr><td>25日(水)</td><td>18:00</td></tr>
</table>
<h2>ビレッジホール(中ホール)</h2>
<table>
<tr><th>開催日</th><th>催物名称</th><th>問合せ</th><th>時間</th><th>料金</th></tr>
<tr><td>23日(月祝)</td><td>access TOUR 2026 PROMPT RUSH</td><td>主催</td><td>17:30</td><td>12,000円</td></tr>
<tr><td>30日(月)</td><td>施設点検日</td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""
items = parse_month(PAGE, "https://example.test/nov")
assert len(items) == 3, items
assert items[0]["title"].startswith("佐野元春")
assert items[1]["start_date"] == "2026-11-24"
assert items[1]["end_date"] == "2026-11-25"
assert items[2]["venue"].endswith("ビレッジホール")
print("PASS")
