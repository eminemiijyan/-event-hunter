from src.append_minokamo_kanko import category_for, parse_events, parse_period

assert parse_period('日時：11月7日（土）・8日（日）', 2026) == ('2026-11-07', '2026-11-08')
assert parse_period('日時：10月24日（土）〜12月27日（日）', 2026) == ('2026-10-24', '2026-12-27')

HTML = '''
<html><body>
<h4>多文化交流DAY 2026</h4><p>日時：11月3日（火） 10:00〜15:00</p><p>場所：ぎふ清流里山公園</p>
<h4>キッチンカー万博2026秋</h4><p>日時：11月7日（土）・8日（日） 11:00〜17:00</p><p>場所：ぎふ清流里山公園</p>
<h4>自然と遊ぶ里山ヨガ</h4><p>日時：11月3日（火）</p><p>場所：ぎふ清流里山公園</p>
<h5>MINOKAMO里山トレイルフェス2026</h5><p>日時：11月29日（日） 8:00〜</p><p>場所：豊田合成健康の森</p>
</body></html>
'''
events = parse_events(HTML, 2026)
assert len(events) == 3
assert events[0]['title'] == '多文化交流DAY 2026'
assert events[1]['start_date'] == '2026-11-07'
assert events[1]['end_date'] == '2026-11-08'
assert events[1]['category'] == 'グルメ'
assert events[2]['category'] == 'スポーツ'
assert category_for('里山イルミネーション2026') == '祭り・季節'
print('PASS')
