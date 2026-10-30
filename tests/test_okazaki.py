from src.append_okazaki import category_for, parse_dates, parse_detail, parse_list

HTML = '''
<html><body>
<article class="spot">
  <div class="dataBox">
    <h3><a href="/event/676">岡崎城下家康公秋まつり <span class="child_site">(岡崎城公園)</span></a></h3>
    <p class="ellipsis">開催期間：11月第1または第2週の土日（2026年は10月31日（土）、11月1日（日））</p>
  </div>
</article>
<article class="spot">
  <div class="dataBox">
    <h3><a href="/event/412">岡崎ジャズストリート <span class="child_site">(ジャズの街岡崎)</span></a></h3>
    <p class="ellipsis">開催期間：毎年11月初旬（2026年は10月31日（土）・1日（日））</p>
  </div>
</article>
<article class="spot">
  <div class="dataBox">
    <h3><a href="/event/6000">オクオカわんぱくまつり2026</a></h3>
    <p class="ellipsis">開催期間：2026年12月5日（土）</p>
  </div>
</article>
<article class="spot">
  <div class="dataBox">
    <h3><a href="/event/7000">オクオカ「京ヶ峯」トレッキング</a></h3>
    <p class="ellipsis">開催期間：2026年11月8日（日）</p>
  </div>
</article>
</body></html>
'''

items = parse_list(HTML)
assert len(items) == 3, items
by_title = {item["title"]: item for item in items}
assert "岡崎城下家康公秋まつり (岡崎城公園)" in by_title
assert "岡崎ジャズストリート (ジャズの街岡崎)" in by_title
assert "オクオカわんぱくまつり2026" in by_title
assert "オクオカ「京ヶ峯」トレッキング" not in by_title

assert parse_dates("11月第1または第2週の土日（2026年は10月31日（土）、11月1日（日））") == (
    "2026-10-31", "2026-11-01"
)
assert parse_dates("毎年11月（2026年は11月21日（土）・22日（日）です。）") == (
    "2026-11-21", "2026-11-22"
)
assert parse_dates("2027年1月1日（元旦）") == ("2027-01-01", "2027-01-01")

DETAIL = '''
<html><body>
<table>
<tr><th>開催期間</th><td>11月第1または第2週の土日（2026年は10月31日（土）、11月1日（日））</td></tr>
<tr><th>開催場所</th><td>乙川河川緑地、岡崎城公園内多目的広場　ほか</td></tr>
</table>
</body></html>
'''

event = parse_detail(
    DETAIL,
    "岡崎城下家康公秋まつり (岡崎城公園)",
    "https://okazaki-kanko.jp/event/676",
)
assert event is not None
assert event["start_date"] == "2026-10-31"
assert event["end_date"] == "2026-11-01"
assert event["venue"] == "乙川河川緑地、岡崎城公園内多目的広場　ほか"
assert event["source"] == "岡崎おでかけナビ"
assert event["category"] == "祭り・季節"
assert category_for("岡崎ジャズストリート") == "コンサート・ショー"
assert category_for("あすおかマーケット") == "グルメ"

print("PASS")
