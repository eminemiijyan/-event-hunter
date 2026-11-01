from datetime import date

from src.append_fukuroi_kanko import (
    discover_articles,
    discover_embedded_events,
    parse_detail_dates,
    parse_detail_venue,
)

listing = '''
<html><body>
<a href="/news/a/">2026.10.27 第4回 ひまわりフェスティバル in みつかわ</a>
<a href="/news/f/">2026.10.27 JR急行 フクロイサイクルトレインが運行されます🚃🚲</a>
<a href="/news/b/">2026.10.20 第2回ふくろいランタンナイト＆大夜市　開催しました</a>
<a href="/news/c/">2026.10.05 袋井 秋の祭典</a>
<a href="/news/d/">2026.08.30 第20回アジア競技大会 女子サッカー エコパ開催日程</a>
<a href="/news/e/">2026.07.01 ふくろい遠州の花火</a>
</body></html>
'''
articles = discover_articles(listing)
assert [x[0] for x in articles] == [
    "第4回 ひまわりフェスティバル in みつかわ",
    "JR急行 フクロイサイクルトレインが運行されます🚃🚲",
    "袋井 秋の祭典",
    "ふくろい遠州の花火",
]

today = date(2026, 10, 31)
detail = '''
<html><body>
<h1>第4回 ひまわりフェスティバル in みつかわ</h1>
<p>📅 開催日：2026年10月31日（土）※小雨決行</p>
<p>📍 場所：JAよりそいプラザ</p>
</body></html>
'''
assert parse_detail_dates(detail, today) == (date(2026, 10, 31), date(2026, 10, 31))
assert parse_detail_venue(detail) == "JAよりそいプラザ"

range_detail = '''
<html><body><p>開催日時：2026年11月28日（土）～2026年11月29日（日）</p><p>会場：袋井市内</p></body></html>
'''
assert parse_detail_dates(range_detail, today) == (date(2026, 11, 28), date(2026, 11, 29))

embedded_detail = '''
<html><body>
<p>11月3日（火・祝）に開催される「どまん中ふくろい 全国だんごまつり」に合わせて列車が運行されます。</p>
<p>さらに当日は、法多山で「どまん中ふくろい 全国だんごまつり」、愛野駅周辺では約100店舗が集まる「あいのマルシェ ハレとケ」も開催されます。</p>
</body></html>
'''
embedded = discover_embedded_events(embedded_detail, date(2026, 11, 1))
assert embedded == [
    ("どまん中ふくろい 全国だんごまつり", date(2026, 11, 3), date(2026, 11, 3), "法多山"),
    ("あいのマルシェ ハレとケ", date(2026, 11, 3), date(2026, 11, 3), "愛野駅周辺"),
]
print("PASS")
