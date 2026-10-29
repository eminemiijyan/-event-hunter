from src.append_portmesse import parse_dates, parse_month

HTML = '''
<html><body>
<article class="calendar-event mc-events multidate">
  <header><h3 class="event-title summary">第1回 中部食品産業創造展’26</h3></header>
  <p>2026年11月4日 – 2026年11月6日</p>
  <p>会場：第1展示館</p>
  <p>お問合せ：日刊工業新聞社</p>
  <a href="https://chubu-shokuten.nikkan.co.jp/">公式</a>
</article>
<article class="calendar-event mc-events multidate">
  <header><h3 class="event-title summary">第1回 中部食品産業創造展’26</h3></header>
  <p>2026年11月4日 – 2026年11月6日</p>
  <p>会場：第1展示館</p>
  <p>お問合せ：日刊工業新聞社</p>
  <a href="https://chubu-shokuten.nikkan.co.jp/">公式</a>
</article>
<article class="calendar-event mc-events">
  <header><h3 class="event-title summary">マイナビインターンシップ＆キャリア発見EXPO 名古屋会場</h3></header>
  <p>2026年11月21日</p>
  <p>会場：第1展示館</p>
  <p>お問合せ：マイナビ</p>
</article>
<article class="calendar-event mc-events multidate">
  <header><h3 class="event-title summary">建設技術フェア2026in中部</h3></header>
  <p>2026年11月19日 – 2026年11月20日</p>
  <p>会場：第1展示館</p>
  <p>お問合せ：運営委員会</p>
  <a href="https://kgf-chubu.com/">公式</a>
</article>
</body></html>
'''

events = parse_month(HTML, "https://portmesse.com/events?month=11&yr=2026&time=month")
assert len(events) == 2, events
food = events[0]
assert food["title"] == "第1回 中部食品産業創造展’26"
assert food["start_date"] == "2026-11-04"
assert food["end_date"] == "2026-11-06"
assert food["venue"] == "ポートメッセなごや 第1展示館"
assert food["category"] == "展示会"
assert food["source"] == "ポートメッセなごや"
assert food["decision"] == "display"
assert food["official_url"] == "https://chubu-shokuten.nikkan.co.jp/"
assert events[1]["title"] == "建設技術フェア2026in中部"

assert parse_dates("2026年11月21日 会場：第1展示館") == ("2026-11-21", "2026-11-21")
print("PASS")
