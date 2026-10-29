from src.append_toyohashi import parse_detail_venue, parse_month

HTML = '''
<html><body>
<ul class="_my_photo_list">
<li>
  <a href="./?Mode=detail&code=997">
    <div class="_my_photo_text">
      <h4>第70回 ええじゃないか豊橋まつり 2026年</h4>
      <div class="_my_photo_note">2026年10月31日(土)～2026年11月1日(日)</div>
    </div>
  </a>
</li>
<li>
  <a href="./?Mode=detail&code=1019">
    <div class="_my_photo_text">
      <h4>第33回 二川宿本陣まつり「大名行列」</h4>
      <div class="_my_photo_note">2026年11月1日(日)～2026年11月1日(日)</div>
    </div>
  </a>
</li>
<li>
  <a href="./?Mode=detail&code=1021">
    <div class="_my_photo_text">
      <h4>とよはしインターナショナルフェスティバル2026</h4>
      <div class="_my_photo_note">2026年11月15日(日)～2026年11月15日(日)</div>
    </div>
  </a>
</li>
<li>
  <a href="./?Mode=detail&code=1030">
    <div class="_my_photo_text">
      <h4>ポケモン天文台 特別企画展</h4>
      <div class="_my_photo_note">2026年9月21日(月)～2026年12月6日(日)</div>
    </div>
  </a>
</li>
<li>
  <a href="./?Mode=detail&code=2000">
    <div class="_my_photo_text">
      <h4>TFM合唱団 第37回定期演奏会</h4>
      <div class="_my_photo_note">2026年11月8日(日)～2026年11月8日(日)</div>
    </div>
  </a>
</li>
</ul>
</body></html>
'''

events = parse_month(HTML)
assert len(events) == 4, events
by_title = {e["title"]: e for e in events}

festival = by_title["第70回 ええじゃないか豊橋まつり 2026年"]
assert festival["start_date"] == "2026-10-31"
assert festival["end_date"] == "2026-11-01"
assert festival["category"] == "祭り・季節"
assert festival["source"] == "ええじゃないか豊橋"
assert festival["official_url"].endswith("?Mode=detail&code=997")

pokemon = by_title["ポケモン天文台 特別企画展"]
assert pokemon["category"] == "ゲーム・アニメ"
assert "TFM合唱団 第37回定期演奏会" not in by_title

DETAIL = '''
<html><body>
<table><tr><th>開催場所</th><td>豊橋市まちなか広場・emCAMPUS EAST</td></tr>
<tr><th>交通機関</th><td>豊橋駅から徒歩5分</td></tr></table>
</body></html>
'''
assert parse_detail_venue(DETAIL) == "豊橋市まちなか広場・emCAMPUS EAST"
print("PASS")
