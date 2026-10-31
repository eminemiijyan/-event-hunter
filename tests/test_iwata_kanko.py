from datetime import date

from src.append_iwata_kanko import (
    _clean_title,
    discover_articles,
    parse_detail_dates,
    parse_detail_venue,
    parse_title_dates,
)

listing = '''
<html><body>
<h3><a href="/2026/10/post-a/">11/7　第21回　遠江国分寺まつり</a></h3>
<h3><a href="/2026/10/post-b/">次回〖11/21〗定期開催！見付宿を歩く</a></h3>
<h3><a href="/2026/10/post-c/">10/24～2/15 磐田駅北口多目的広場イルミネーション</a></h3>
<h3><a href="/2026/10/post-d/">〖磐田市初開催〗音楽体験イベント ～クリスタルピアノの自由演奏～</a></h3>
</body></html>
'''
articles = discover_articles(listing)
assert [x[0] for x in articles] == [
    "11/7 第21回 遠江国分寺まつり",
    "10/24～2/15 磐田駅北口多目的広場イルミネーション",
    "〖磐田市初開催〗音楽体験イベント ～クリスタルピアノの自由演奏～",
]

today = date(2026, 10, 31)
assert parse_title_dates(articles[0][0], today) == (date(2026, 11, 7), date(2026, 11, 7))
assert parse_title_dates(articles[1][0], today) == (date(2026, 10, 24), date(2027, 2, 15))
assert _clean_title(articles[0][0]) == "第21回 遠江国分寺まつり"
assert _clean_title(articles[1][0]) == "磐田駅北口多目的広場イルミネーション"

detail = '''
<html><body>
<h1>音楽体験イベント</h1>
<p>開催日時◆令和8年11月7日（土）10時00分～18時00分・8日（日）9時30分～16時30分</p>
<p>会場◆磐田市民文化会館「かたりあ」 創造活動室3</p>
<p>入場料・参加費◆無料</p>
<p>お問い合わせ◆磐田市文化振興課</p>
</body></html>
'''
assert parse_detail_dates(detail, today) == (date(2026, 11, 7), date(2026, 11, 8))
assert parse_detail_venue(detail) == "磐田市民文化会館「かたりあ」 創造活動室3"

festival = '''
<html><body>
<p>開催日◆令和8年11月7日（土）</p>
<p>開催場所◆遠江国分寺史跡公園</p>
<p>遠江国分寺まつり実行委員会 HP チラシはこちら タイムスケジュールはこちら</p>
</body></html>
'''
assert parse_detail_venue(festival) == "遠江国分寺史跡公園"
print("PASS")
