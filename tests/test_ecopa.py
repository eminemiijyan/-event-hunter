from src.append_ecopa import parse_listing

page = '''
<html><body>
<a href="/event/detail/1/">2026.11.08 公園 エコパ自主事業 FDG in エコパ</a>
<a href="/event/detail/2/">2026.11.08 公園 エコパ自主事業 エコパココ SPORTS PARK OPEN DAY 2026</a>
<a href="/event/detail/3/">2026.12.11 エコパアリーナ コンサート GENERATIONS</a>
<a href="/event/detail/4/">2026.12.18 エコパアリーナ コンサート THE ALFEE</a>
<a href="/event/detail/4/">2026.12.19 エコパアリーナ コンサート THE ALFEE</a>
</body></html>
'''
items = parse_listing(page)
assert [x["title"] for x in items] == ["エコパココ SPORTS PARK OPEN DAY 2026", "GENERATIONS", "THE ALFEE"]
assert items[2]["start_date"] == "2026-12-18"
assert items[2]["end_date"] == "2026-12-19"
print("PASS")
