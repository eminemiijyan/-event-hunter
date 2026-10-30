from src.append_actcity import parse_month

page = '''
<html><body>
<div class="event"><span>11/3(火)</span><h4><a href="/event/detail/?id=1">転職・就職イベント シゴトフェア</a></h4><p>場 所 展示イベントホール 第1ブロック 時 間 11:00</p></div>
<div class="event"><span>11/8(日)</span><h4><a href="/event/detail/?id=2">第79回全日本合唱コンクール全国大会 小学生部門</a></h4><p>場 所 大ホール 時 間 10:00</p></div>
<div class="event"><span>11/14(土) ｜ 11/16(月)</span><h4><a href="/event/detail/?id=3">第10回静岡国際オペラコンクール 第1次予選</a></h4><p>場 所 大ホール 時 間 13:30</p></div>
<div class="event"><span>11/6(金)</span><h4><a href="/event/detail/?id=4">オルガンミニコンサート No.123</a></h4><p>場 所 中ホール 時 間 12:30</p></div>
</body></html>
'''
items = parse_month(page, 2026)
assert [x["title"] for x in items] == ["第79回全日本合唱コンクール全国大会 小学生部門", "第10回静岡国際オペラコンクール 第1次予選"]
assert items[0]["start_date"] == "2026-11-08"
assert items[1]["start_date"] == "2026-11-14"
assert items[1]["end_date"] == "2026-11-16"
print("PASS")
