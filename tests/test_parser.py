from src.fetch_events import parse_events

SAMPLE = """
<html><body>
<section class="event">
<p>2026.11.07 (Sat) - 2026.11.08 (Sun)</p>
<h3>名古屋キャンピングカーフェア2026 AUTUMN</h3>
<p>その他</p>
<p>会場 ホールF、多目的利用地</p>
<a href="https://example.com/camper">イベント公式HPへ</a>
</section>
<section class="event">
<p>2026.11.14 (Sat) - 2026.11.15 (Sun)</p>
<h3>FIELD STYLE EXPO 2026</h3>
<p>展示会</p>
<p>会場 ホールC、D、E、F、多目的利用地</p>
<a href="https://example.com/field">イベント公式HPへ</a>
</section>
</body></html>
"""

events = parse_events(SAMPLE, "https://www.aichiskyexpo.com/ase-event/?ym=202611")
assert len(events) == 2, events
assert events[0].title == "名古屋キャンピングカーフェア2026 AUTUMN"
assert events[0].start_date == "2026-11-07"
assert events[0].end_date == "2026-11-08"
assert events[0].venue == "ホールF、多目的利用地"
assert events[0].official_url == "https://example.com/camper"
assert events[1].category == "展示会"
print("PASS")
