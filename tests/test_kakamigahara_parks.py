from src.append_kakamigahara_parks import category_for, parse_events, parse_reiwa_date

assert parse_reiwa_date('令和8年11月3日（火曜日）') == '2026-11-03'
assert parse_reiwa_date('令和8年11月21日（土曜日）') == '2026-11-21'

HTML = '''
<html><body>
<h2>市民公園</h2>
<h3>令和8年11月3日（火曜日）</h3>
<h4>マーケット日和2026</h4>
<p>種別：キッチンカー・物販</p>
<p>開催時間：10時～16時</p>
<h3>令和8年11月8日（日曜日）</h3>
<h4>LINK UP TOGETHER</h4>
<p>種別：音楽・キッチンカー</p>
<h2>学びの森</h2>
<h3>令和8年10月31日（土曜日）</h3>
<h4>Halloween Party＆マルシェ</h4>
<p>種別：キッチンカー・物販・体験</p>
</body></html>
'''
events = parse_events(HTML)
assert len(events) == 3
assert events[0]['title'] == 'マーケット日和2026'
assert events[0]['venue'] == '市民公園'
assert events[0]['start_date'] == '2026-11-03'
assert events[0]['category'] == 'グルメ'
assert events[1]['category'] == 'グルメ'
assert events[2]['venue'] == '学びの森'
assert category_for('市民音楽祭', '音楽') == 'コンサート・ショー'
print('PASS')
