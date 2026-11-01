from src.append_oasispark import category_for, extract_cards, parse_period

assert parse_period('2026.12/5(土)～27(日)土日開催') == ('2026-12-05', '2026-12-27')
assert parse_period('2026.11/14(土)～2027.3/31(水)') == ('2026-11-14', '2027-03-31')
assert parse_period('2026.11/14(土)15(日)12/5(土)6(日)') == ('2026-11-14', '2026-12-06')

HTML = '''
<html><body>
<article>
  <div>2026.12/5(土)～27(日)土日開催、平日無し※荒天中止</div>
  <h2><a href="/event/2026/10/6127/">キャンドルナイト2026</a></h2>
</article>
<article>
  <div>2026.11/14(土)～2027.3/31(水) 土日・祝日・季節休み期間に開催</div>
  <h2><a href="https://www.oasispark.co.jp/event/2026/10/9999/">食べれる！ニジマス釣堀</a></h2>
</article>
</body></html>
'''
cards = extract_cards(HTML)
assert len(cards) == 2
assert cards[0]['title'] == 'キャンドルナイト2026'
assert cards[0]['start_date'] == '2026-12-05'
assert cards[0]['end_date'] == '2026-12-27'
assert cards[1]['start_date'] == '2026-11-14'
assert cards[1]['end_date'] == '2027-03-31'
assert category_for('キャンドルナイト2026') == '祭り・季節'
assert category_for('AUTUMN CYCLE FESTA 2026') == 'スポーツ'
assert category_for('ものづくり体験') == 'イベント'
print('PASS')
