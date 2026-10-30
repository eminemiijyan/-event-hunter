from src.append_ise_kanko import parse_listing

HTML = '''
<html><body>
<a href="/event/lecture/">2026.09.15(火) 〜 2026.10.09(金) 第１７回観光交流伊勢会議　基調講演</a>
<a href="/event/ise-matsuri/">2026.10.10(土) 〜 2026.10.11(日) 令和８年伊勢まつり</a>
<a href="/event/hatsuho/">2026.10.15(木) 〜 2026.10.16(金) 令和８年第五十五回神嘗奉祝祭　初穂曳について</a>
<a href="/event/rakuichi/">2026.10.31(土) 〜 2026.11.01(日) 2026秋の伊勢楽市</a>
</body></html>
'''

events = parse_listing(HTML)
assert len(events) == 3, events
assert events[0]["title"] == "令和８年伊勢まつり"
assert events[0]["start_date"] == "2026-10-10"
assert events[0]["end_date"] == "2026-10-11"
assert events[1]["category"] == "祭り・季節"
assert events[2]["title"] == "2026秋の伊勢楽市"
assert events[2]["end_date"] == "2026-11-01"
assert all(e["source"] == "伊勢市観光協会" for e in events)
assert all("講演" not in e["title"] for e in events)
print("PASS")
