from src.append_mie_culture import parse_events

HTML = '''
<html><body>
<section class="event-card">
  <h2>ベルギー国立管弦楽団</h2>
  <p>開催期間：2026年11月3日（火曜祝日）</p>
  <p>開催場所：三重県文化会館 大ホール</p>
  <a href="/event/detail/60001">詳細情報</a>
</section>
<section class="event-card">
  <h2>劇団アンパサンド「立ち止まるには近すぎる」</h2>
  <p>開催期間：2026年11月8日（日曜日）</p>
  <p>開催場所：三重県文化会館 小ホール</p>
  <a href="/event/detail/60002">詳細情報</a>
</section>
<section class="event-card">
  <h2>MPAD2026</h2>
  <p>開催期間：2026年11月12日（木曜日）～13日（金曜日）</p>
  <p>開催場所：津市内飲食店ほか</p>
  <a href="/event/detail/60003">詳細情報</a>
</section>
<section class="event-card">
  <h2>ワンコインコンサート　オーボエ　金子亜未</h2>
  <p>開催期間：2026年11月13日（金曜日）</p>
  <p>開催場所：三重県文化会館 大ホール</p>
  <a href="/event/detail/60004">詳細情報</a>
</section>
<section class="event-card">
  <h2>竹田モモコ×内藤裕敬「他人」</h2>
  <p>開催期間：2026年12月5日（土曜日）～6日（日曜日）</p>
  <p>開催場所：三重県文化会館 小ホール</p>
  <a href="/event/detail/60005">詳細情報</a>
</section>
</body></html>
'''

events = parse_events(HTML)
assert len(events) == 3, events
assert events[0]["title"] == "ベルギー国立管弦楽団"
assert events[0]["start_date"] == "2026-11-03"
assert events[0]["venue"] == "三重県文化会館 大ホール"
assert events[1]["title"].startswith("劇団アンパサンド")
assert events[2]["title"] == "竹田モモコ×内藤裕敬「他人」"
assert events[2]["start_date"] == "2026-12-05"
assert events[2]["end_date"] == "2026-12-06"
assert all(e["source"] == "三重県文化会館" for e in events)
assert all("MPAD" not in e["title"] for e in events)
assert all("ワンコイン" not in e["title"] for e in events)
print("PASS")
