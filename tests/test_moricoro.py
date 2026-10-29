from src.append_moricoro import parse_events

HTML = '''
<html><body>
<ul class="p-moricoro__event__list">
<li class="p-moricoro__event__list__triger">
  <article>
    <time class="p-moricoro__event__list__time"><span>2026-11-08</span></time>
    <section><h3>長久手市商工会まつり</h3></section>
  </article>
  <div>会場：愛・地球博記念公園（モリコロパーク） 三日月休憩所前 主催：長久手市商工会</div>
</li>
<li class="p-moricoro__event__list__triger">
  <article>
    <time class="p-moricoro__event__list__time"><span>2026-11-14</span></time>
    <section><h3>あいちサトラボ収穫祭</h3></section>
  </article>
  <div>開催日時：2026年11月14日（土）10:00～15:00</div>
</li>
<li class="p-moricoro__event__list__triger">
  <article>
    <time class="p-moricoro__event__list__time"><span>2026-11-23</span></time>
    <section><h3>Let's エコアクション in Aichi</h3></section>
  </article>
  <div>会場：地球市民交流センター ※入場料：無料</div>
  <a href="https://www.pref.aichi.jp/press-release/ecoactionr08.html">愛知県HP</a>
</li>
<li class="p-moricoro__event__list__triger">
  <article>
    <time class="p-moricoro__event__list__time"><span>2026-11-23</span></time>
    <section><h3>モリコロパーク秋まつり</h3></section>
  </article>
  <div>三日月休憩所で秋まつりを開催します。</div>
</li>
<li class="p-moricoro__event__list__triger">
  <article>
    <time class="p-moricoro__event__list__time"><span>2026-11-22</span></time>
    <section><h3>世界に一つだけ MYコースターづくり</h3></section>
  </article>
  <div>場所：日本庭園「香流亭」茶室</div>
</li>
</ul>
</body></html>
'''

events = parse_events(HTML)
assert len(events) == 4, events
by_title = {e["title"]: e for e in events}

merchant = by_title["長久手市商工会まつり"]
assert merchant["start_date"] == "2026-11-08"
assert merchant["end_date"] == "2026-11-08"
assert merchant["category"] == "祭り・季節"
assert merchant["source"] == "モリコロパーク"
assert "三日月休憩所前" in merchant["venue"]

eco = by_title["Let's エコアクション in Aichi"]
assert eco["category"] == "その他"
assert eco["official_url"] == "https://www.pref.aichi.jp/press-release/ecoactionr08.html"
assert eco["venue"].endswith("地球市民交流センター")

fall = by_title["モリコロパーク秋まつり"]
assert fall["venue"].endswith("三日月休憩所")

assert "世界に一つだけ MYコースターづくり" not in by_title
print("PASS")
