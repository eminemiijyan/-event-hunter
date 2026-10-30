from src.append_gifu_guide import discover_listing_pages, extract_detail_links, parse_dates, parse_detail

INDEX = '''
<html><body>
<a href="/event/detail_1092.html">中津川ふるさとじまん祭・菓子まつり</a>
<a href="/event/detail_983.html">下石どえらあええ陶器祭り</a>
<a href="/event/index_1_2_16___0__.html">2</a>
</body></html>
'''

pages = discover_listing_pages(INDEX)
assert pages[0].endswith('/event/index.html')
assert pages[1].endswith('/event/index_1_2_16___0__.html')
links = extract_detail_links(INDEX)
assert len(links) == 2
assert links[0].endswith('detail_1092.html')

assert parse_dates('2026年10月23日（金）・24日（土）・25日（日）') == ('2026-10-23', '2026-10-25')
assert parse_dates('2026年10月24日（土）～11月30日（月）') == ('2026-10-24', '2026-11-30')

DETAIL = '''
<html><body>
<h1>中津川ふるさとじまん祭・菓子まつり</h1>
<div>カテゴリー</div><div>祭り・伝統行事 グルメ</div>
<dl>
<dt>開催期間</dt><dd>2026年10月23日（金）・24日（土）・25日（日）</dd>
<dt>開催場所</dt><dd>東美濃ふれあいセンター</dd>
</dl>
</body></html>
'''
item = parse_detail(DETAIL, 'https://www.kankou-gifu.jp/event/detail_1092.html')
assert item is not None
assert item['start_date'] == '2026-10-23'
assert item['end_date'] == '2026-10-25'
assert item['venue'] == '東美濃ふれあいセンター'
assert item['category'] == 'グルメ'

SMALL = '''
<html><body>
<h1>初心者向け少人数ヨガ教室</h1>
<dl><dt>開催期間</dt><dd>2026年11月1日</dd><dt>開催場所</dt><dd>公民館</dd></dl>
</body></html>
'''
assert parse_detail(SMALL, 'https://example.test/small') is None
print('PASS')
