from datetime import date

from src.append_kakegawa_kanko import parse_events

page = '''
<html><body>
<p>〖イベント情報〗</p>
<p>・11/14　11/28　松ヶ岡一般公開日（第2・4土曜日）</p>
<p>・9/15-11/23　97歳セツの新聞ちぎり絵原画展（二の丸美術館）</p>
<p>・10/22-11/15　原泉アートデイズ</p>
<p>・10/30-3/28　つま恋イルミネーション</p>
<p>・10/31　掛川百鬼夜行 第五夜</p>
<p>・10/31　だいとう・おおすか軽便ロマンウォーク</p>
<p>・11/1　小笠神社 矢矧祭</p>
<p>・11/3　第45回掛川商工まつり</p>
<p>・11/3　掛川城もみじまつり</p>
<p>・11/3　しんきんグルメサミット＠三の丸広場</p>
<p>・11/7　第十七夜 月夜の茶会</p>
<p>・11/14-15　フラワーフェスティバル＠生涯学習センター</p>
<p>〖観光施設の営業情報〗</p>
</body></html>
'''
items = parse_events(page, date(2026, 10, 31))
assert [x["title"] for x in items] == [
    "原泉アートデイズ",
    "つま恋イルミネーション",
    "掛川百鬼夜行 第五夜",
    "小笠神社 矢矧祭",
    "しんきんグルメサミット",
    "掛川城もみじまつり",
    "第45回掛川商工まつり",
    "フラワーフェスティバル",
]
assert items[1]["start_date"] == "2026-10-30"
assert items[1]["end_date"] == "2027-03-28"
assert next(x for x in items if x["title"] == "しんきんグルメサミット")["venue"] == "三の丸広場"
assert next(x for x in items if x["title"] == "フラワーフェスティバル")["end_date"] == "2026-11-15"
print("PASS")
