from src.append_gifu_parks import parse_events

HTML = '''
<html><body><main>
<h1>岐阜市内公園のイベント情報</h1>
<p>岐阜公園・岐阜城楽市 〖秋まつり〗</p>
<p>開催日：11月14日（土曜）～11月15日（日曜）</p>
<p>午前10時～午後4時</p>
<p>リバーパークおぶさ 〖ひかりとものがたり花火大会〗</p>
<p>開催日：10月31日（土曜） 午後6時～午後7時30分</p>
<p>金公園 〖秋酒祭 岐阜2026〗</p>
<p>開催日：10月24日（土曜） 午前11時～午後6時30分</p>
<p>10月25日（日曜） 午前11時～午後5時30分</p>
<p>岐阜公園 〖菊人形・菊花展〗</p>
<p>開催日：10月下旬〜11月下旬</p>
</main></body></html>
'''

events = parse_events(HTML, 2026)
assert len(events) == 3
assert events[0]['title'] == '秋まつり'
assert events[0]['start_date'] == '2026-11-14'
assert events[0]['end_date'] == '2026-11-15'
assert events[0]['category'] == '祭り・季節'
assert events[1]['category'] == '祭り・季節'
assert events[2]['title'] == '秋酒祭 岐阜2026'
assert events[2]['start_date'] == '2026-10-24'
assert events[2]['end_date'] == '2026-10-25'
assert events[2]['category'] == 'グルメ'
assert all('菊人形' not in e['title'] for e in events)
print('PASS')
