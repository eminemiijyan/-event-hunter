from src.append_ogaki_family import category_for, parse_dates, parse_events

assert parse_dates('令和8年11月14日（土）・15日（日）', 2026) == ('2026-11-14', '2026-11-15')
assert parse_dates('11月2日（月）〜15日（日） 11月16日（月）〜30日（月）', 2026) == ('2026-11-02', '2026-11-30')

HTML = '''
<html><body>
<h3>秋のこどもまんなか水都っ子月間中のイベント紹介</h3>
<h4>ちいさな一歩を応援！子育て・つながりフェスティバル</h4>
<p>とき 令和8年11月7日（土）10時〜14時</p><p>ところ イオンモール大垣 1階 太陽の広場</p><p>内容 体験コーナー</p>
<h4>キッズワークフェス in おおがき 2026</h4>
<p>とき 令和8年11月14日（土）・15日（日）9時〜15時30分</p><p>ところ 大垣城ホール、大垣公園、大垣市役所ほか</p><p>内容 職業体験</p>
<h4>いっしょにあそぼ！わくわく吹奏楽コンサート</h4>
<p>とき 令和8年11月22日（日）10時～</p><p>ところ 大垣市児童館 遊戯室</p><p>内容 親子で楽しめるコンサート</p>
</body></html>
'''
events = parse_events(HTML, 2026)
assert len(events) == 3
assert events[0]['title'].startswith('ちいさな一歩')
assert events[1]['end_date'] == '2026-11-15'
assert events[1]['venue'] == '大垣城ホール、大垣公園、大垣市役所ほか'
assert events[2]['category'] == 'コンサート・ショー'
assert category_for('みんなで楽しむボッチャ体験') == 'スポーツ'
print('PASS')
