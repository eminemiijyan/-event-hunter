from src.append_kani_city import (
    category_for,
    discover_listing_pages,
    extract_detail_links,
    parse_dates,
    parse_detail,
    parse_subevents,
)

assert parse_dates('令和8年11月13日（金）、14日（土）、20日（金）、21日（土）、22日（日）') == ('2026-11-13', '2026-11-22')
assert parse_dates('令和9年1月31日(日)') == ('2027-01-31', '2027-01-31')

LIST_HTML = '''
<html><body>
<a href="/item/29471.htm">美濃桃山陶の聖地 ライトアップイベント 緋色の杜</a>
<a href="/item/10951.htm">可児市健康フェスタinカニミライブを開催します！</a>
<a href="/item/99999.htm">ベビークラス（0歳児学級）に参加しませんか？</a>
<a href="/dd.aspx?_PickUp_para=15&moduleid=30570&pfromid=15">次の一覧へ</a>
</body></html>
'''
links = extract_detail_links(LIST_HTML)
assert len(links) == 2
assert links[0][1] == 'https://www.city.kani.lg.jp/item/29471.htm'
pages = discover_listing_pages(LIST_HTML)
assert len(pages) == 2

DETAIL_HTML = '''
<html><body>
<h1>美濃桃山陶の聖地 ライトアップイベント 緋色の杜</h1>
<h4>日時</h4><p>令和8年11月13日（金）、14日（土）、20日（金）、21日（土）、22日（日）</p>
<h4>場所</h4><p>荒川豊蔵資料館</p>
</body></html>
'''
events = parse_detail(DETAIL_HTML, 'https://www.city.kani.lg.jp/item/29471.htm')
assert len(events) == 1
assert events[0]['start_date'] == '2026-11-13'
assert events[0]['end_date'] == '2026-11-22'
assert events[0]['venue'] == '荒川豊蔵資料館'
assert events[0]['category'] == '祭り・季節'

SUBEVENT_HTML = '''
<html><body>
<h1>チャンバラ合戦－可児市の乱－ 決戦の地 山城に行こう！</h1>
<p>イベント名：木曽川こどもひろば2026 開催日：令和8年10月25日(日) 時間：10時30分 会場：日特スパークテックWKSパーク 定員：100名</p>
<p>イベント名：大道芸フェスティバル 開催日：令和8年11月21日(土)、22日(日) 時間：10時30分 会場：ぎふワールド・ローズガーデン 定員：100名</p>
<p>イベント名：山城に行こう！2026 ～決戦～ 開催日：令和9年1月31日(日) 時間：10時 会場：広見地区センター 定員：なし</p>
</body></html>
'''
subevents = parse_subevents(SUBEVENT_HTML, 'https://www.city.kani.lg.jp/26110.htm')
assert len(subevents) == 3
assert subevents[1]['title'] == '大道芸フェスティバル'
assert subevents[1]['start_date'] == '2026-11-21'
assert subevents[1]['end_date'] == '2026-11-22'
assert subevents[1]['venue'] == 'ぎふワールド・ローズガーデン'
assert category_for('アーラでeスポ初開催') == 'ゲーム'
print('PASS')
