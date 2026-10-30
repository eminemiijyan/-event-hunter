from src.append_gifu_ncc import parse_events

HTML = '''
<html><body>
<h3>2026年11月 催し物案内</h3>
<table>
<tr><th>開催日</th><th>開催場所</th><th>催し物名</th><th>時間</th><th>料金</th></tr>
<tr><td>18(水)</td><td>メインホール</td><td>キーウ・クラシック・バレエ くるみ割り人形</td><td>18:30～</td><td>指定席5,000円</td></tr>
<tr><td>21(土)～22(日)</td><td>国際会議室ほか</td><td>日本産業看護学会第15回学術集会</td><td>---</td><td>関係者</td></tr>
<tr><td>22(日)</td><td>メインホール</td><td>岐阜県交響楽団第105回定期演奏会</td><td>14:00～</td><td>一般2,000円</td></tr>
</table>
<h3>2026年12月 催し物案内</h3>
<table>
<tr><th>開催日</th><th>開催場所</th><th>催し物名</th><th>時間</th><th>料金</th></tr>
<tr><td>31(木)～1/1(金)</td><td>メインホール</td><td>年越しコンサート</td><td>23:00～</td><td>全席指定</td></tr>
</table>
</body></html>
'''

events = parse_events(HTML)
assert len(events) == 3
assert events[0]['title'].startswith('キーウ')
assert events[0]['category'] == 'コンサート・ショー'
assert events[0]['start_date'] == '2026-11-18'
assert events[1]['title'].startswith('岐阜県交響楽団')
assert events[2]['start_date'] == '2026-12-31'
assert events[2]['end_date'] == '2027-01-01'
assert all('学術集会' not in e['title'] for e in events)
print('PASS')
