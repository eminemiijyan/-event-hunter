from src.append_oasis21 import _is_duplicate, category_for, is_major, parse_dates, parse_month

SAMPLE = """
<div id="event_calendar">
  <div class="box_days">
    <ul>
      <li class="news_item">
        <a class="has_arrow" href="https://www.sakaepark.co.jp/?p=8077">
          <div class="info">
            <span class="date">2026年11月01日(Sun)</span>
            <span class="news_category">銀河の広場</span>
            <strong><span>栄まちじゅう音楽広場</span></strong>
          </div>
        </a>
      </li>
      <li class="news_item">
        <a class="has_arrow" href="https://www.sakaepark.co.jp/?p=8054">
          <div class="info">
            <span class="date">2026年11月03日(Tue)</span>
            <span class="news_category">銀河の広場</span>
            <strong><span>パンマルシェ26</span></strong>
          </div>
        </a>
      </li>
      <li class="news_item">
        <a class="has_arrow" href="https://www.sakaepark.co.jp/?p=7779">
          <div class="info">
            <span class="date">2026年11月02日(Mon)</span>
            <span class="news_category">銀河の広場</span>
            <strong><span>2026年度 警察音楽隊「街角コンサート」</span></strong>
          </div>
        </a>
      </li>
      <li class="news_item">
        <a class="has_arrow" href="https://www.sakaepark.co.jp/?p=1381">
          <div class="info">
            <span class="date">毎週土曜日</span>
            <span class="news_category">オアシス２１</span>
            <strong><span>オーガニックファーマーズ朝市村</span></strong>
          </div>
        </a>
      </li>
    </ul>
  </div>
</div>
"""

items = parse_month(SAMPLE)
assert len(items) == 2
assert items[0]["title"] == "栄まちじゅう音楽広場"
assert items[0]["start_date"] == "2026-11-01"
assert items[0]["venue"] == "オアシス21・銀河の広場"
assert items[0]["category"] == "コンサート・ショー"
assert items[1]["title"] == "パンマルシェ26"
assert items[1]["category"] == "グルメ・マーケット"

assert is_major("2026スポNAGOフェス")
assert is_major("パンマルシェ26")
assert not is_major("オアシス２１日曜アトリエ ワークショップ")
assert not is_major("警察音楽隊 街角コンサート")
assert parse_dates("2026年09月19日(Sat)〜2026年10月04日(Sun)") == ("2026-09-19", "2026-10-04")
assert parse_dates("毎週土曜日") is None
assert category_for("スポNAGOフェス") == "スポーツ"

candidate = {"title": "パンマルシェ26", "start_date": "2026-11-03"}
assert _is_duplicate({"title": "パンマルシェ26 in オアシス21", "start_date": "2026-11-03"}, candidate)
assert not _is_duplicate({"title": "パンマルシェ26", "start_date": "2026-11-04"}, candidate)

print("PASS")
