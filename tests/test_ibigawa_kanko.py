from src.append_ibigawa_kanko import category_for, parse_dates, parse_events

assert parse_dates('11月14日（土曜日）、15日（日曜日）', 2026, 11) == ('2026-11-14', '2026-11-15')
assert parse_dates('11月22日（日曜日）', 2026, 11) == ('2026-11-22', '2026-11-22')

HTML = '''
<html><body>
<h2>令和8年11月イベント情報</h2>
<table>
<tr><th>日にち</th><th>行事</th><th>場所</th><th>問い合わせ</th></tr>
<tr><td>11月8日（日曜日）</td><td>いびがわマラソン2026</td><td>揖斐川町内</td><td>事務局</td></tr>
<tr><td>11月14日（土曜日）、15日（日曜日）</td><td>第10回いびがわ産業フェスティバル</td><td>揖斐川町地域交流センター「はなもも」</td><td>役場</td></tr>
<tr><td>11月15日（日曜日）</td><td>横蔵寺もみじまつり</td><td>横蔵寺駐車場</td><td>観光プラザ</td></tr>
<tr><td>11月22日（日曜日）</td><td>谷汲もみじまつり</td><td>町営谷汲門前駐車場</td><td>観光プラザ</td></tr>
</table>
</body></html>
'''
events = parse_events(HTML)
assert len(events) == 4
assert events[0]['title'] == 'いびがわマラソン2026'
assert events[1]['end_date'] == '2026-11-15'
assert events[2]['category'] == '祭り・季節'
assert category_for('谷汲もみじまつり') == '祭り・季節'
print('PASS')
