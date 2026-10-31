from datetime import date

from src.append_yaizu_kanko import discover_monthly_pages, parse_dates, parse_events

category_html = '''
<html><body>
<a href="/news/9942">〖2026年10月〗焼津の行事・イベントご紹介</a>
<a href="/news/10028">〖2026年11月〗焼津の行事・イベント</a>
<a href="/news/9800">2026年9月の焼津のイベントご紹介</a>
<a href="/news/11000">〖2027年4月〗焼津の行事・イベント</a>
</body></html>
'''
assert discover_monthly_pages(category_html, date(2026, 10, 31)) == [
    (2026, 10, "https://www.yaizu.gr.jp/news/9942"),
    (2026, 11, "https://www.yaizu.gr.jp/news/10028"),
]

assert parse_dates("2026年11月14日（土）・15日（日）10:00～15:00", 2026, 11) == (
    date(2026, 11, 14), date(2026, 11, 15)
)
assert parse_dates("2026年11月28日（土）14:00～20:00 11月29日（日）10:00～16:00", 2026, 11) == (
    date(2026, 11, 28), date(2026, 11, 29)
)
assert parse_dates("2026年11月19日（木）～2027年1月31日（日）", 2026, 11) == (
    date(2026, 11, 19), date(2027, 1, 31)
)
assert parse_dates("2026年11月7日（土）（1日限定開催/予備日11月8日（日））", 2026, 11) == (
    date(2026, 11, 7), date(2026, 11, 7)
)

page_html = '''
<html><body>
<p>焼津神社朝市「壱の市」</p>
<div>開催期間</div><div>2026年11月1日（日）9:00～14:00</div>
<div>場所</div><div>焼津神社 参道</div>
<div>関連リンク先</div>

<p>おおいがわフェア2026</p>
<div>開催期間</div><div>2026年11月3日（火・祝）9:00～13:00</div>
<div>場所</div><div>大井川文化会館（ミュージコ）及び駐車場</div><div>大井川地域交流センター</div>
<div>関連リンク先</div>

<p>〖延期開催〗第17回やいづ浜通り 夏のあかり展</p>
<div>開催期間</div><div>2026年11月7日（土）（1日限定開催/予備日11月8日（日））</div>
<p>※当初日程：9月4日・5日</p>
<div>場所</div><div>焼津市浜通り（八雲通り）城之腰地区</div>
<div>関連リンク先</div>

<p>〖市制75周年〗魚（とと）フェス～焼津超大漁祭～</p>
<div>開催期間</div><div>2026年11月14日（土）・15日（日）10:00～15:00</div>
<div>場所</div><div>焼津漁港新港特設会場</div>
<div>関連リンク先</div>

<p>焼津ライトアップ・イルミネーション2026</p>
<div>開催期間</div><div>2026年11月19日（木）～2027年1月31日（日）</div>
<div>場所</div><div>JR焼津駅南口</div>
<div>関連リンク先</div>

<p>ピックヨウル ～海の街のクリスマスマーケット2026～</p>
<div>開催期間</div><div>2026年11月28日（土）14:00～20:00</div><div>11月29日（日）10:00～16:00</div>
<div>場所</div><div>石津西公園みなく～る</div>
<div>関連リンク先</div>
</body></html>
'''

events = parse_events(page_html, "https://www.yaizu.gr.jp/news/10028", 2026, 11, date(2026, 10, 31))
assert [e["title"] for e in events] == [
    "おおいがわフェア2026",
    "〖延期開催〗第17回やいづ浜通り 夏のあかり展",
    "〖市制75周年〗魚(とと)フェス~焼津超大漁祭~",
    "焼津ライトアップ・イルミネーション2026",
    "ピックヨウル ~海の街のクリスマスマーケット2026~",
]
assert events[0]["venue"] == "大井川文化会館(ミュージコ)及び駐車場 大井川地域交流センター"
assert events[1]["start_date"] == events[1]["end_date"] == "2026-11-07"
assert events[2]["end_date"] == "2026-11-15"
assert events[3]["end_date"] == "2027-01-31"
assert events[4]["end_date"] == "2026-11-29"
assert all(e["source"] == "焼津市観光協会" for e in events)
print("PASS")
