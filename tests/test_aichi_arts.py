from src.append_aichi_arts import parse_dates, parse_events

assert parse_dates("2026年11月21日（土）・22日（日）") == ("2026-11-21", "2026-11-22")
assert parse_dates("2026年12月24日（木）") == ("2026-12-24", "2026-12-24")

HTML = """
<html><body>
<div class="event-card">
  <div>2026年11月21日（土）・22日（日）</div>
  <a href="/event/detail/a.html">AICHI NEXT： Performing Arts Project〈Challenge stage B〉</a>
</div>
<div class="event-card">
  <div>2026年12月5日（土）・6日（日）</div>
  <a href="/event/detail/b.html">ルサンチカ『ゴドーを待ちながら』</a>
</div>
<div class="event-card">
  <div>2026年11月5日（木）</div>
  <a href="/event/detail/c.html">第24回AAF戯曲賞【募集】</a>
</div>
</body></html>
"""
items = parse_events(HTML)
assert len(items) == 2, items
assert items[0]["end_date"] == "2026-11-22"
assert items[1]["category"] == "コンサート・ショー"
print("PASS")
