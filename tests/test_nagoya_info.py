from src.append_nagoya_info import category_for, discover_candidate_links, discover_pages, parse_dates, parse_detail

LIST_SAMPLE = '''
<html><body>
<div class="event-slider-item"><a class="tdn" href="/event/detail/664/"><div class="event-slider-con"><p>栄・伏見</p><h4 class="event-slider-name">台湾・台中夜市2026</h4><dl class="box-spot-now"><dt></dt><dd>2026年10月31日(土) ～ 11月3日(火･祝)</dd><dt></dt><dd>久屋大通公園 エディオン久屋広場</dd></dl></div></a></div>
<div class="event-slider-item"><a class="tdn" href="/event/detail/1413/"><div class="event-slider-con"><h4 class="event-slider-name">特別陳列 ここ中村で60年</h4></div></a></div>
<a href="/event?tdate=2026-10-31&page=3#search_ret_top">3</a>
</body></html>
'''
links = discover_candidate_links(LIST_SAMPLE)
assert links == ["https://www.nagoya-info.jp/event/detail/664/"]
assert discover_pages(LIST_SAMPLE) == 3

DETAIL = '''
<html><body>
<h1>台湾・台中夜市2026</h1>
<table>
<tr><th>日程</th><td>2026年10月31日（土）～11月3日(火･祝)</td></tr>
<tr><th>時間</th><td>12:00～21:00</td></tr>
<tr><th>開催場所</th><td>久屋大通公園　エディオン久屋広場</td></tr>
<tr><th>料金</th><td>無料</td></tr>
</table>
</body></html>
'''
e = parse_detail(DETAIL, "https://www.nagoya-info.jp/event/detail/664/")
assert e is not None
assert e["title"] == "台湾・台中夜市2026"
assert e["start_date"] == "2026-10-31"
assert e["end_date"] == "2026-11-03"
assert e["venue"] == "久屋大通公園 エディオン久屋広場"
assert e["category"] == "グルメ"
assert e["decision"] == "display"

assert parse_dates("2026年12月31日～1月2日") == ("2026-12-31", "2027-01-02")
assert category_for("覚王山秋祭2026") == "祭り・季節"
assert category_for("ホシガオカ COFFEE MARKET Oct.-Nov.") == "グルメ"
print("PASS")
