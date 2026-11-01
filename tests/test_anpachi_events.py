from src.append_anpachi_events import category_for, extract_event_links, parse_dates, parse_detail

INDEX_HTML = '''
<html><body>
<h2>イベント情報</h2>
<a href="/0000002682.html">「五味太郎　絵本出版年代記展」記念　五味太郎さんトークショーの開催について</a>
<a href="/0000002681.html">「五味太郎　絵本出版年代記展」開催</a>
<a href="/0000002600.html">【11月7日、8日】安八ふれあい祭り2026を開催します！</a>
<h2>まちのできごと</h2>
<a href="/0000009999.html">別の記事</a>
</body></html>
'''
links = extract_event_links(INDEX_HTML)
assert len(links) == 3
assert links[0][1] == 'https://www.town.anpachi.lg.jp/0000002682.html'

assert parse_dates('2026年11月21日（土）～12月20日（日）') == ('2026-11-21', '2026-12-20')
assert parse_dates('令和8年11月21日（土曜日）') == ('2026-11-21', '2026-11-21')

DETAIL = '''
<html><body>
<h1>「五味太郎　絵本出版年代記展」開催</h1>
<p>開催日時　2026年11月21日（土）～12月20日（日）</p>
<p>場所　　　ハートピア安八 1階 歴史民俗資料館</p>
</body></html>
'''
event = parse_detail(DETAIL, 'fallback', 'https://www.town.anpachi.lg.jp/0000002681.html')
assert event is not None
assert event['start_date'] == '2026-11-21'
assert event['end_date'] == '2026-12-20'
assert event['venue'] == 'ハートピア安八 1階 歴史民俗資料館'
assert event['category'] == '展示会'
assert category_for('安八ふれあい祭り2026') == '祭り・季節'
print('PASS')
