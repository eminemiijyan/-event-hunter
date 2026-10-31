from src.append_fukiage import month_pairs, parse_events

HTML = '''
<html><body>
<div>一般有料吹上ホール</div>
<div>11月21日(土)～11月22日(日) ナゴヤレプタイルズワールド2026</div>
<p>日本最大級の爬虫両生類の展示即売会。</p>
<p>主催：実行委員会</p>

<div>招待無料吹上ホール</div>
<div>11月25日(水)～11月26日(木) 業界商談会2026</div>
<p>招待者向け展示会</p>

<div>一般無料第1ファッション</div>
<div>11月27日(金) スポナビキャリアセミナー2028</div>
<p>学生向け就職セミナー</p>

<div>一般有料第1ファッション</div>
<div>11月29日(日) コミックライブ in 名古屋</div>
<p>アマチュアコミック作品の展示即売会</p>

<div>一般無料吹上ホール、第1ファッション</div>
<div>12月4日(金)～12月5日(土) 名証IRエキスポ2026</div>
<p>上場企業が集まる大型イベント</p>
</body></html>
'''

events = parse_events(HTML, 2026, 'https://www.nipc.or.jp/fukiage/event/?m=11&y=2026')
by_title = {e['title']: e for e in events}

assert 'ナゴヤレプタイルズワールド2026' in by_title
assert by_title['ナゴヤレプタイルズワールド2026']['start_date'] == '2026-11-21'
assert by_title['ナゴヤレプタイルズワールド2026']['end_date'] == '2026-11-22'
assert by_title['ナゴヤレプタイルズワールド2026']['venue'] == '名古屋市中小企業振興会館（吹上ホール）'

assert '業界商談会2026' not in by_title
assert 'スポナビキャリアセミナー2028' not in by_title
assert 'コミックライブ in 名古屋' in by_title
assert by_title['コミックライブ in 名古屋']['category'] == 'ゲーム'
assert '名証IRエキスポ2026' in by_title

pairs = month_pairs(__import__('datetime').date(2026, 11, 1), 3)
assert pairs == [(2026, 11), (2026, 12), (2027, 1)]

print('PASS')
