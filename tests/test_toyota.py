from src.append_toyota import category_for, parse_dates, parse_month

HTML = '''
<html><body>
<div class="monthly_event_box">
  <a href="/spots/detail/2252/"><p class="monthly_event_area"><span class="area">豊田</span></p></a>
  <div class="monthly_event_txt">
    <h2><a href="/spots/detail/2252/">とよた産業フェスタ2026</a></h2>
    <dl><dt>開催日・期間：</dt><dd>2026年10月31日(土) ～ 11月1日(日)</dd></dl>
    <dl><dt>開催場所：</dt><dd>豊田スタジアム<br/>豊田市千石町7-2</dd></dl>
  </div>
</div>
<div class="monthly_event_box">
  <a href="/spots/detail/2554/"><p class="monthly_event_area"><span class="area">旭</span></p></a>
  <div class="monthly_event_txt">
    <h2><a href="/spots/detail/2554/">KIRABOSHI FES.2026</a></h2>
    <dl><dt>開催日・期間：</dt><dd>2026年11月7日(土)、11月8日(日)</dd></dl>
    <dl><dt>開催場所：</dt><dd>旭高原元気村<br/>豊田市旭八幡町根山68-1</dd></dl>
  </div>
</div>
<div class="monthly_event_box">
  <a href="/spots/detail/30114/"><p class="monthly_event_area"><span class="area">豊田</span></p></a>
  <div class="monthly_event_txt">
    <h2><a href="/spots/detail/30114/">名古屋グランパス VS 京都サンガF.C.</a></h2>
    <dl><dt>開催日・期間：</dt><dd>2026年11月7日(土)</dd></dl>
    <dl><dt>開催場所：</dt><dd>豊田スタジアム<br/>豊田市千石町7-2</dd></dl>
  </div>
</div>
<div class="monthly_event_box">
  <a href="/spots/detail/2308/"><p class="monthly_event_area"><span class="area">足助</span></p></a>
  <div class="monthly_event_txt">
    <h2><a href="/spots/detail/2308/">旧鈴木家住宅保存修理工事エリア見学ツアー</a></h2>
    <dl><dt>開催日・期間：</dt><dd>2026年11月7日(土)</dd></dl>
    <dl><dt>開催場所：</dt><dd>旧鈴木家住宅</dd></dl>
  </div>
</div>
</body></html>
'''

items = parse_month(HTML, default_year=2026)
assert len(items) == 3, items
by_title = {item["title"]: item for item in items}
assert "とよた産業フェスタ2026" in by_title
assert "KIRABOSHI FES.2026" in by_title
assert "名古屋グランパス VS 京都サンガF.C." in by_title
assert "旧鈴木家住宅保存修理工事エリア見学ツアー" not in by_title
assert by_title["とよた産業フェスタ2026"]["venue"] == "豊田スタジアム"
assert by_title["KIRABOSHI FES.2026"]["start_date"] == "2026-11-07"
assert by_title["KIRABOSHI FES.2026"]["end_date"] == "2026-11-08"

assert parse_dates("2026年10月31日(土) ～ 11月1日(日)") == (
    "2026-10-31", "2026-11-01"
)
assert parse_dates("2026年9月26日(土)～1月31日(日)") == (
    "2026-09-26", "2027-01-31"
)
assert category_for("とよた産業フェスタ2026") == "展示会"
assert category_for("名古屋グランパス VS 京都サンガF.C.") == "スポーツ"
assert category_for("第71回 香嵐渓もみじまつり") == "祭り・季節"

print("PASS")
