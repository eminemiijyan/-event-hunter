from src.append_actcity import collapse_contiguous, parse_month

page = '''
<html><body>
<div class="event"><span>11/3(火)</span><h4><a href="/event/detail/?id=1">転職・就職イベント シゴトフェア</a></h4><p>場 所 展示イベントホール 第1ブロック 時 間 11:00</p></div>
<div class="event"><span>11/8(日)</span><h4><a href="/event/detail/?id=2">第79回全日本合唱コンクール全国大会 小学生部門</a></h4><p>場 所 大ホール 時 間 10:00</p></div>
<div class="event"><span>11/14(土) ｜ 11/16(月)</span><h4><a href="/event/detail/?id=3">第10回静岡国際オペラコンクール 第1次予選</a></h4><p>場 所 大ホール 時 間 13:30</p></div>
<div class="event"><span>11/6(金)</span><h4><a href="/event/detail/?id=4">オルガンミニコンサート No.123</a></h4><p>場 所 中ホール 時 間 12:30</p></div>
<div class="event"><span>11/20(金)</span><h4><a href="/event/detail/?id=5">第58回暴力追放と交通事故・薬物乱用防止市民大会</a></h4><p>場 所 大ホール 時 間 13:00</p></div>
<div class="event"><span>11/21(土)</span><h4><a href="/event/detail/?id=6">マイナビ就活直前フェア浜松会場</a></h4><p>場 所 展示イベントホール 時 間 12:00</p></div>
</body></html>
'''
items = parse_month(page, 2026)
assert [x["title"] for x in items] == ["第79回全日本合唱コンクール全国大会 小学生部門", "第10回静岡国際オペラコンクール 第1次予選"]
assert items[0]["start_date"] == "2026-11-08"
assert items[1]["start_date"] == "2026-11-14"
assert items[1]["end_date"] == "2026-11-16"

miss_saigon = [
    {"title": "ミュージカル『ミス・サイゴン』", "start_date": "2027-01-08", "end_date": "2027-01-08", "venue": "アクトシティ浜松 大ホール", "official_url": "a"},
    {"title": "ミュージカル『ミス・サイゴン』", "start_date": "2027-01-09", "end_date": "2027-01-09", "venue": "アクトシティ浜松 大ホール", "official_url": "b"},
    {"title": "ミュージカル『ミス・サイゴン』", "start_date": "2027-01-10", "end_date": "2027-01-10", "venue": "アクトシティ浜松 大ホール", "official_url": "c"},
    {"title": "ミュージカル『ミス・サイゴン』", "start_date": "2027-01-11", "end_date": "2027-01-11", "venue": "アクトシティ浜松 大ホール", "official_url": "d"},
]
collapsed = collapse_contiguous(miss_saigon)
assert len(collapsed) == 1
assert collapsed[0]["start_date"] == "2027-01-08"
assert collapsed[0]["end_date"] == "2027-01-11"
print("PASS")
