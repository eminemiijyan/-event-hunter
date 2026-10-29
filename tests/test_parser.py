from src.fetch_events import Event, classify_event, parse_events, parse_ig_api, parse_kyodo_events

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
assert events[0].decision == "display"
assert events[1].category == "展示会"
assert events[1].decision == "display"

base = dict(
    start_date="2026-10-30",
    end_date="2026-10-30",
    venue="ホールC",
    prefecture="愛知県",
    category="その他",
    source="Aichi Sky Expo",
    official_url="https://example.com",
)

private_event = classify_event(Event(title="プライベートイベント", **base))
assert private_event.decision == "exclude"

family_sale = classify_event(Event(title="オンワード秋のファミリーセール", **base))
assert family_sale.decision == "hold"

kids_shogi = classify_event(Event(title="将棋日本シリーズJTプロ公式戦/テーブルマークこども大会 東海大会", **base))
assert kids_shogi.decision == "hold"

ig_payload = {
    "data": [
        {
            "id": 2017,
            "date": "2026年11月1日（日）",
            "title": "りそなグループ B.LEAGUE 2026-27 B.LEAGUE PREMIER リーグ戦　名古屋ダイヤモンドドルフィンズ vs 滋賀レイクス",
            "link": "2017",
        },
        {
            "id": 2014,
            "date": "2026年11月7日（土）",
            "title": "HOSHIMACHI SUISEI ARENA TOUR 2026 Once Upon a Stellar",
            "link": "2014",
        },
        {
            "id": 2013,
            "date": "2026年11月13日（金）・11月14日（土）",
            "title": "緑黄色社会 ARENA TOUR 2026 \"あたまご\"",
            "link": "2013",
        },
    ]
}

ig_events = parse_ig_api(ig_payload, "2026-11")
assert len(ig_events) == 3
assert ig_events[0].start_date == "2026-11-01"
assert ig_events[0].end_date == "2026-11-01"
assert ig_events[0].category == "スポーツ"
assert ig_events[0].decision == "display"
assert ig_events[0].official_url == "https://www.ig-arena.jp/events/2017/"
assert ig_events[1].category == "コンサート・ショー"
assert ig_events[1].decision == "display"
assert ig_events[2].start_date == "2026-11-13"
assert ig_events[2].end_date == "2026-11-14"
assert ig_events[2].source == "IGアリーナ"

KYODO_SAMPLE = """
<div class="eventlistbox">
  <dl>
    <dt>【公演名 / アーティスト名】 <a class="alink" href="/events/detail/3693">&amp;TEAM</a>
    【公演日】 2026年11月09日（月） 【開場 / 開演】 16:30 / 17:30</dt>
    <dd>【会場名】 愛知県芸術劇場 大ホール 【料金】 指定席 16,500円</dd>
  </dl>
  <dl>
    <dt>【公演名 / アーティスト名】 <a class="alink" href="/events/detail/9998">小規模ライブ</a>
    【公演日】 2026年11月10日（火） 【開場 / 開演】 18:00 / 19:00</dt>
    <dd>【会場名】 HeartLand 【料金】 全自由 4,000円</dd>
  </dl>
  <dl>
    <dt>【公演名 / アーティスト名】 <a class="alink" href="/events/detail/9999">県外公演</a>
    【公演日】 2026年11月11日（水） 【開場 / 開演】 18:00 / 19:00</dt>
    <dd>【会場名】 三重県文化会館 大ホール 【料金】 指定席 8,000円</dd>
  </dl>
  <dl>
    <dt>【公演名 / アーティスト名】 <a class="alink" href="/events/detail/9997">【中止】テスト公演</a>
    【公演日】 2026年11月12日（木） 【開場 / 開演】 18:00 / 19:00</dt>
    <dd>【会場名】 Zepp Nagoya 【料金】 指定席 8,000円</dd>
  </dl>
</div>
"""

kyodo_events = parse_kyodo_events(KYODO_SAMPLE)
assert len(kyodo_events) == 3, kyodo_events
assert kyodo_events[0].title == "&TEAM"
assert kyodo_events[0].start_date == "2026-11-09"
assert kyodo_events[0].venue == "愛知県芸術劇場 大ホール"
assert kyodo_events[0].decision == "display"
assert kyodo_events[0].official_url == "https://www.kyodotokai.co.jp/events/detail/3693"
assert kyodo_events[1].venue == "HeartLand"
assert kyodo_events[1].decision == "hold"
assert kyodo_events[2].decision == "exclude"
assert all(e.venue != "三重県文化会館 大ホール" for e in kyodo_events)

print("PASS")
