from datetime import date

from src.append_shizuoka_city import discover_candidates, parse_dates, parse_detail

listing = '''
<html><body>
<h3>大道芸ワールドカップ in 静岡2026</h3>
<div><a href="detail_690.html">詳細を見る</a></div>
<h3>清水港船宿記念館「次郎長映画を楽しむ」</h3>
<div><a href="detail_702.html">詳細を見る</a></div>
<h3>静岡市美術館　わたしたちのルノワール</h3>
<div><a href="detail_669.html">詳細を見る</a></div>
<h3>日帰りの自転車旅♪「オクシズの赤鬼ライド」</h3>
<div><a href="detail_707.html">詳細を見る</a></div>
<h3>ホビーのまち静岡　クリスマスフェスタ2026</h3>
<div><a href="detail_706.html">詳細を見る</a></div>
</body></html>
'''
assert discover_candidates(listing) == [
    ("大道芸ワールドカップ in 静岡2026", "https://www.visit-shizuoka.com/event/detail_690.html"),
    ("静岡市美術館 わたしたちのルノワール", "https://www.visit-shizuoka.com/event/detail_669.html"),
    ("ホビーのまち静岡 クリスマスフェスタ2026", "https://www.visit-shizuoka.com/event/detail_706.html"),
]

today = date(2026, 10, 31)
assert parse_dates("2026年10月31日（土）～11月3日（火・祝）", today) == (date(2026, 10, 31), date(2026, 11, 3))
assert parse_dates("2026年12月12日（土）～12月13日（日）", today) == (date(2026, 12, 12), date(2026, 12, 13))

detail = '''
<html><body>
<dl>
<dt>開催期間</dt><dd>2026年11月7日（土）～11月14日（土）</dd>
<dt>開催場所</dt><dd>赤水の滝</dd>
</dl>
</body></html>
'''
assert parse_detail(detail, today) == (date(2026, 11, 7), date(2026, 11, 14), "赤水の滝")
print("PASS")
