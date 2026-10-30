from src.append_suzuka import parse_calendar, parse_date_span

HTML = '''
<html><body>
<div>[2026年] レース／イベントカレンダー</div>
<h4>10月October</h4>
<p>10月3日（土）～11月15日（日）</p>
<div>パークイベント</div>
<a>コチラミッション！秋のプッチタウンフェスティバル</a>
<p>10月3日（土）・4日（日）</p>
<div>4輪レース</div>
<a>2026 SUZUKA CHAMPION CUP RACE Round 4</a><span>｜ フルコース</span>
<p>10月24日（土）・25日（日）</p>
<div>2輪レース</div>
<a>2026 MFJ全日本ロードレース選手権シリーズ 第7戦 第58回 MFJグランプリ スーパーバイクレース in 鈴鹿</a><span>｜ フルコース</span>
<h4>11月November</h4>
<p>11月21日（土）～12月27日（日）</p>
<div>パークイベント</div>
<a>冬のワクワクいっぱい！コチラファミリーのクリスマスホリデー</a>
<p>11月21日（土）・22日（日）</p>
<div>4輪レース</div>
<a>2026年 全日本スーパーフォーミュラ選手権 第11戦・第12戦 第25回JAF鈴鹿グランプリ</a><span>｜ フルコース</span>
<p>11月28日（土）</p>
<div>2輪レース</div>
<a>FUN&amp;RUN! 2-Wheels</a><span>｜ フルコース</span>
</body></html>
'''

events = parse_calendar(HTML)
assert len(events) == 4, events
assert events[0]["title"] == "コチラミッション！秋のプッチタウンフェスティバル"
assert events[0]["start_date"] == "2026-10-03"
assert events[0]["end_date"] == "2026-11-15"
assert events[0]["prefecture"] == "三重県"
assert events[0]["category"] == "祭り・季節"
assert events[1]["category"] == "スポーツ"
assert "MFJグランプリ" in events[1]["title"]
assert events[2]["end_date"] == "2026-12-27"
assert "スーパーフォーミュラ" in events[3]["title"]
assert all("CHAMPION CUP" not in e["title"] for e in events)
assert all("FUN&RUN" not in e["title"] for e in events)

start, end = parse_date_span("11月7日（土）・8日（日）", 2026)
assert start.isoformat() == "2026-11-07"
assert end.isoformat() == "2026-11-08"
start, end = parse_date_span("2025年12月31日（水）～1月4日（日）", 2026)
assert start.isoformat() == "2025-12-31"
assert end.isoformat() == "2026-01-04"
print("PASS")
