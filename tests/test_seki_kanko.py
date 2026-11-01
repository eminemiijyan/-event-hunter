from src.append_seki_kanko import discover_listing_pages, extract_detail_links, parse_dates, parse_detail

INDEX = '''
<html><body>
<a href="/event/detail_5056.html">関の工場参観日2026</a>
<a href="/event/detail_5150.html">セキ日和 Autumn 2026</a>
<a href="/event/index_1_2__33.html">2</a>
</body></html>
'''

pages = discover_listing_pages(INDEX)
assert pages[0].endswith('/event/index.html')
assert pages[1].endswith('/event/index_1_2__33.html')
links = extract_detail_links(INDEX)
assert len(links) == 2
assert links[0].endswith('detail_5056.html')

assert parse_dates('2026年11月12日（木）、13日（金）、14日（土）') == ('2026-11-12', '2026-11-14')
assert parse_dates('2026年11月14日（土）、12月12日（土）、2027年1月9日（土）') == ('2026-11-14', '2027-01-09')

DETAIL = '''
<html><body>
<h1>セキ日和 Autumn 2026</h1>
<div>カテゴリ</div><div>飲食イベント・マルシェ</div>
<dl>
<dt>開催期間</dt><dd>2026年11月14日（土）</dd>
<dt>開催場所</dt><dd>本町3丁目～8丁目、古民家あいせき、本町チャレンジBASE</dd>
</dl>
</body></html>
'''
item = parse_detail(DETAIL, 'https://sekikanko.jp/event/detail_5150.html')
assert item is not None
assert item['start_date'] == '2026-11-14'
assert item['end_date'] == '2026-11-14'
assert item['venue'].startswith('本町3丁目')
assert item['category'] == 'グルメ'
assert item['source'] == 'せき観光ナビ'

FACTORY = '''
<html><body>
<h1>関の工場参観日2026</h1>
<div>カテゴリ</div><div>体験イベント</div>
<dl>
<dt>開催期間</dt><dd>2026年11月12日（木）、13日（金）、14日（土）</dd>
<dt>開催場所</dt><dd>せきてらす・参加事業所の工場</dd>
</dl>
</body></html>
'''
factory = parse_detail(FACTORY, 'https://sekikanko.jp/event/detail_5056.html')
assert factory is not None
assert factory['start_date'] == '2026-11-12'
assert factory['end_date'] == '2026-11-14'

SMALL = '''
<html><body>
<h1>初心者向け少人数ヨガ教室</h1>
<dl><dt>開催期間</dt><dd>2026年11月8日</dd><dt>開催場所</dt><dd>公民館</dd></dl>
</body></html>
'''
assert parse_detail(SMALL, 'https://example.test/small') is None
print('PASS')
