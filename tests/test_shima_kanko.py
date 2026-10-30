from src.append_shima_kanko import parse_listing

HTML = '''
<html><body>
<a href="/event/20570/">〖イベント〗消防フェスタ 2026 開催！ 2026.11.07 (土) 〜 2026.11.07 (土)</a>
<a href="/event/20532/">観光農園×道の駅×物産館 オータムキャンペーン2026 2026.11.08 (日) 〜 2026.11.08 (日)</a>
<a href="/event/20372/">〖イベント〗きらりんMARCHE開催！〖2026年11月15日(日)〗 2026.11.15 (日) 〜 2026.11.15 (日)</a>
<a href="/event/20535/">〖イベント〗志摩スペイン村「スパークリング・クリスマス」開催！ 2026.11.21 (土) 〜 2026.12.25 (金)</a>
<a href="/event/20600/">〖キャンペーン〗志摩市観光協会 公式Instagram投稿キャンペーン 2026.11.01 (日) 〜 2026.11.30 (月)</a>
<a href="/event/20200/">〖イベント〗第13回 伊勢志摩サイクリングフェスティバル2026 開催！ 2026.11.29 (日) 〜 2026.11.29 (日)</a>
<a href="/event/20510/">〖年末年始〗大晦日は約250発の花火！グランドメルキュール伊勢志摩リゾート＆スパでお正月イベント 2026.12.31 (木) 〜 2027.01.03 (日)</a>
</body></html>
'''

events = parse_listing(HTML)
titles = [e["title"] for e in events]
assert titles == [
    "消防フェスタ 2026 開催!",
    "観光農園×道の駅×物産館 オータムキャンペーン2026",
    "きらりんMARCHE開催!〖2026年11月15日(日)〗",
    "第13回 伊勢志摩サイクリングフェスティバル2026 開催!",
], titles
assert events[0]["start_date"] == "2026-11-07"
assert events[1]["start_date"] == "2026-11-08"
assert events[-1]["category"] == "祭り・季節" or events[-1]["category"] == "スポーツ"
assert all(e["source"] == "志摩市観光協会" for e in events)
assert all("志摩スペイン村" not in e["title"] for e in events)
assert all("Instagram" not in e["title"] for e in events)
assert all("グランドメルキュール" not in e["title"] for e in events)
print("PASS")
