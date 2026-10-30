from src.append_shima_spain import parse_listing

HTML = '''
<html><body>
<a href="https://nazoxnazo.com/foo">リアル謎解きゲーム 期間：2026/2/14〜2027/1/11</a>
<a href="/event/detail.html?id=20">新VRアトラクション「THE SUNSET OF MARS」 期間：2026/7/4〜2026/11/1</a>
<a href="/special/autumn2026.html">ハロウィーンフィエスタ 期間：2026/9/18〜2026/11/2</a>
<a href="/event/detail.html?id=31">スパークリング・クリスマス 期間：2026/11/21〜2026/12/25</a>
<a href="/event/detail.html?id=32">さよならテソロ・デ・オーロ 期間：2026/11/3〜2027/1/11</a>
</body></html>
'''

events = parse_listing(HTML)
assert [e["title"] for e in events] == [
    "ハロウィーンフィエスタ",
    "さよならテソロ・デ・オーロ",
    "スパークリング・クリスマス",
]
assert events[0]["start_date"] == "2026-09-18"
assert events[0]["end_date"] == "2026-11-02"
assert events[1]["venue"] == "志摩スペイン村"
assert all(e["source"] == "志摩スペイン村" for e in events)
print("PASS")
