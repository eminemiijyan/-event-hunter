from datetime import date

from src.append_shizuoka_city import discover_candidates, parse_dates, parse_detail

listing = '''
<html><body>
<h3>大道芸ワールドカップ in 静岡2026</h3>
<h4>静岡市内の各所が大道芸のステージに変わります！</h4>
<div><a href="detail_690.html">詳細を見る</a></div>
<h3>清水港船宿記念館「次郎長映画を楽しむ」</h3>
<h4>映画とトークを楽しむ</h4>
<div><a href="detail_702.html">詳細を見る</a></div>
<h3>静岡市美術館　わたしたちのルノワール</h3>
<h4>ルノワール39点、今秋、静岡市美術館へ。</h4>
<div><a href="detail_669.html">詳細を見る</a></div>
<h3>赤水の滝ライトアップ</h3>
<h4>梅ヶ島温泉郷の紅葉と滝のライトアップをお楽しみください！</h4>
<div><a href="detail_696.html">詳細を見る</a></div>
<h3>清水港 冬の花火クルーズ</h3>
<h4>冬の澄みきった夜空を彩る大迫力の海上花火！</h4>
<div><a href="detail_694.html">詳細を見る</a></div>
<h3>日帰りの自転車旅♪「オクシズの赤鬼ライド」</h3>
<div><a href="detail_707.html">詳細を見る</a></div>
<h3>ホビーのまち静岡　クリスマスフェスタ2026</h3>
<div><a href="detail_706.html">詳細を見る</a></div>
</body></html>
'''
assert discover_candidates(listing) == [
    ("大道芸ワールドカップ in 静岡2026", "https://www.visit-shizuoka.com/event/detail_690.html"),
    ("静岡市美術館 わたしたちのルノワール", "https://www.visit-shizuoka.com/event/detail_669.html"),
    ("赤水の滝ライトアップ", "https://www.visit-shizuoka.com/event/detail_696.html"),
    ("ホビーのまち静岡 クリスマスフェスタ2026", "https://www.visit-shizuoka.com/event/detail_706.html"),
]

today = date(2026, 10, 31)
assert parse_dates("2026年10月31日（土）～11月3日（火・祝）", today) == (date(2026, 10, 31), date(2026, 11, 3))
assert parse_dates("2026年12月12日（土）～12月13日（日）", today) == (date(2026, 12, 12), date(2026, 12, 13))

detail_table = '''
<html><body>
<dl>
<dt>開催期間</dt><dd>2026年11月7日（土）～11月14日（土）</dd>
<dt>開催場所</dt><dd>赤水の滝</dd>
</dl>
</body></html>
'''
assert parse_detail(detail_table, today) == (date(2026, 11, 7), date(2026, 11, 14), "赤水の滝")

detail_inline = '''
<html><body>
<p>〖開催期間〗2026年11月7日（土）～11月14日（土）</p>
<p>〖開催場所〗赤水の滝（静岡市葵区・梅ヶ島温泉郷）</p>
<p>〖ライトアップ時間〗17:30～19:30</p>
<p>●手筒花火・和太鼓演奏</p>
<p>場所：赤水の滝ライトアップ臨時駐車場</p>
<p>問合せ：静岡市葵区地域総務課</p>
</body></html>
'''
assert parse_detail(detail_inline, today) == (
    date(2026, 11, 7),
    date(2026, 11, 14),
    "赤水の滝(静岡市葵区・梅ヶ島温泉郷)",
)

# Ordinary prose containing the word 会場 must never be treated as a venue label.
detail_museum = '''
<html><body>
<dl>
<dt>開催期間</dt><dd>2026年9月22日（火）～11月15日（日）</dd>
<dt>開催場所</dt><dd>静岡市美術館</dd>
</dl>
<p>ぜひ会場で、ルノワールが描いた光と色彩をお楽しみください。</p>
</body></html>
'''
assert parse_detail(detail_museum, today) == (
    date(2026, 9, 22),
    date(2026, 11, 15),
    "静岡市美術館",
)

# If no venue label exists, a clearly named major venue in the official page is a safe fallback.
detail_serizawa = '''
<html><body>
<p>開催期間：2026年10月10日（土）～12月13日（日）</p>
<p>静岡市立芹沢銈介美術館で開催します。ぜひ会場でお楽しみください。</p>
</body></html>
'''
assert parse_detail(detail_serizawa, today) == (
    date(2026, 10, 10),
    date(2026, 12, 13),
    "芹沢銈介美術館",
)

detail_christmas = '''
<html><body>
<p>開催期間：2026年12月12日（土）～12月13日（日）</p>
<p>ホビーのまち静岡 クリスマスフェスタ2026はツインメッセ静岡で開催します。</p>
</body></html>
'''
assert parse_detail(detail_christmas, today) == (
    date(2026, 12, 12),
    date(2026, 12, 13),
    "ツインメッセ静岡",
)
print("PASS")
