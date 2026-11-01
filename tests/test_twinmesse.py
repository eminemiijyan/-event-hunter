from datetime import date

from src.append_twinmesse import parse_events

HTML = '''
<html><body>
<h5>10/31 静岡ハンドメイドマルシェ2026</h5>
<div>10月31日(土)・11月1日(日)11：00～17：00</div>
<div>〖会場〗北館大展示場</div>
<div>〖主催〗実行委員会</div>
<div>〖催事内容〗全国のクリエイターによるハンドメイド・クラフト作品の展示・販売</div>

<h5>11/12 カネカ食品 静岡支店 地域商談会</h5>
<div>11月12日(木)10：00～16：00</div>
<div>〖会場〗北館第3小展示場</div>
<div>〖催事内容〗パン食材を中心とした試食展示会</div>

<h5>11/21 タミヤフェア2026</h5>
<div>11月21日(土)・22日(日)</div>
<div>21日 9：00～17：00</div>
<div>22日 9：00～16：00</div>
<div>〖会場〗北館大展示場・南館大展示場</div>
<div>〖主催〗株式会社タミヤ</div>
<div>〖催事内容〗電動RCカーレース、ミニ四駆イベント、スケールモデル展示及び販売</div>

<h5>11/28 産業フェアしずおか2026</h5>
<div>11月28日(土)・29日(日)9：30～16：00</div>
<div>〖会場〗北館大展示場・南館大展示場</div>
<div>〖催事内容〗静岡市と近隣の産業・企業が多数出展</div>
</body></html>
'''

events = parse_events(HTML, date(2026, 10, 31))
by_title = {e['title']: e for e in events}

assert '静岡ハンドメイドマルシェ2026' in by_title
assert by_title['静岡ハンドメイドマルシェ2026']['start_date'] == '2026-10-31'
assert by_title['静岡ハンドメイドマルシェ2026']['end_date'] == '2026-11-01'
assert by_title['静岡ハンドメイドマルシェ2026']['venue'] == 'ツインメッセ静岡 北館大展示場'

assert 'カネカ食品 静岡支店 地域商談会' not in by_title
assert 'タミヤフェア2026' in by_title
assert by_title['タミヤフェア2026']['category'] == 'ゲーム'
assert by_title['タミヤフェア2026']['end_date'] == '2026-11-22'
assert '産業フェアしずおか2026' in by_title

print('PASS')
