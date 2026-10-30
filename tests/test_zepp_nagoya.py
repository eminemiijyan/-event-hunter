from src.append_zepp_nagoya import _same_zepp_event, display_title, parse_month

SAMPLE = """
<html><body>
<a class="sch-content" href="https://www.zepp.co.jp/hall/nagoya/schedule/single/?rid=1">
  <div class="sch-content-date"><p class="sch-content-date__year">2026</p><p class="sch-content-date__month">11.3</p></div>
  <div class="sch-content-text"><h2 class="sch-content-text__performer">Hump Back</h2><h3 class="sch-content-text__ttl">Hump Back pre. \"HELLO ANEW TOUR\"2026-2027</h3></div>
</a>
<a class="sch-content" href="https://www.zepp.co.jp/hall/nagoya/schedule/single/?rid=2">
  <div class="sch-content-date"><p class="sch-content-date__year">2026</p><p class="sch-content-date__month">11.4</p></div>
  <div class="sch-content-text"><h2 class="sch-content-text__performer">04 Limited Sazabys</h2><h3 class="sch-content-text__ttl">ONE MAN TOUR 2026</h3></div>
</a>
</body></html>
"""

items = parse_month(SAMPLE)
assert len(items) == 2
assert items[0]["start_date"] == "2026-11-03"
assert items[0]["title"] == 'Hump Back pre. "HELLO ANEW TOUR"2026-2027'
assert items[1]["start_date"] == "2026-11-04"
assert items[1]["title"] == "04 Limited Sazabys — ONE MAN TOUR 2026"
assert display_title("甲斐よしひろ", "甲斐よしひろ ホームカミングツアー2026") == "甲斐よしひろ ホームカミングツアー2026"

candidate = {
    "title": "04 Limited Sazabys — ONE MAN TOUR 2026",
    "performer": "04 Limited Sazabys",
    "raw_title": "ONE MAN TOUR 2026",
    "start_date": "2026-11-04",
}
assert _same_zepp_event(
    {"title": "04 Limited Sazabys", "start_date": "2026-11-04", "venue": "Zepp Nagoya"},
    candidate,
)
assert not _same_zepp_event(
    {"title": "04 Limited Sazabys", "start_date": "2026-11-05", "venue": "Zepp Nagoya"},
    candidate,
)

print("PASS")
