from src.append_seino_suitrip import category_for, parse_date_line, parse_events

assert parse_date_line('11月1日', 11, 2026, 11) == ('2026-11-01', '2026-11-01')
assert parse_date_line('11月7日・8日', 11, 2026, 11) == ('2026-11-07', '2026-11-08')
assert parse_date_line('1月10日', 1, 2026, 11) == ('2027-01-10', '2027-01-10')
assert parse_date_line('11月上旬', 11, 2026, 11) is None

HTML = '''
<html><body>
<h2>11月</h2>
<div>11月1日</div><div>城下町大垣きもの園遊会（秋）</div><div>大垣駅通りほか　(大垣市)</div>
<div>11月3日</div><div>木育フェア2026</div><div>大野町運動公園　(大野町)</div>
<div>11月上旬</div><div>安八ふれあい祭り</div><div>安八町役場　(安八町)</div>
<div>11月14日</div><div>もとす遊RUN2026</div><div>根尾地域　(本巣市)</div>
<h2>12月</h2>
<div>12月13日</div><div>おおがきマラソン2026</div><div>大垣駅通りほか　(大垣市)</div>
</body></html>
'''
events = parse_events(HTML, 2026, 11)
assert len(events) == 4
assert events[0]['title'] == '城下町大垣きもの園遊会(秋)'
assert events[0]['venue'] == '大垣駅通りほか (大垣市)'
assert events[1]['title'] == '木育フェア2026'
assert events[2]['start_date'] == '2026-11-14'
assert events[2]['category'] == 'スポーツ'
assert events[3]['start_date'] == '2026-12-13'
assert category_for('城下町大垣イルミネーション') == '祭り・季節'
print('PASS')
