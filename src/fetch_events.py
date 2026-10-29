from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

SKY_BASE = "https://www.aichiskyexpo.com"
SKY_LIST_URL = SKY_BASE + "/ase-event/?ym={ym}"
IG_BASE = "https://www.ig-arena.jp"
IG_API_URL = IG_BASE + "/api/events/month?month={ym}"
IG_EVENT_URL = IG_BASE + "/events/{event_id}/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

SKY_DATE_RE = re.compile(
    r"(?P<sy>\d{4})\.(?P<sm>\d{2})\.(?P<sd>\d{2})"
    r"\s*\([^)]+\)\s*-\s*"
    r"(?P<ey>\d{4})\.(?P<em>\d{2})\.(?P<ed>\d{2})"
    r"\s*\([^)]+\)"
)
JP_DATE_RE = re.compile(r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日")

CATEGORIES = {
    "その他", "ゲーム", "コンサート・ショー", "スポーツ", "セミナー・シンポジウム", "展示会"
}
EXCLUDE_WORDS = (
    "プライベートイベント", "招待者限定", "招待制", "関係者限定", "関係者のみ",
    "一般入場不可", "一般非公開", "社内イベント", "企業内イベント",
)
HOLD_WORDS = ("ファミリーセール", "こども大会", "子ども大会", "キッズ大会")
DISPLAY_CATEGORIES = {"展示会", "コンサート・ショー", "スポーツ", "ゲーム"}
DISPLAY_WORDS = (
    "フェス", "フェア", "EXPO", "エキスポ", "展示会", "モーターショー", "キャンピングカー",
    "コンサート", "ライブ", "ショー", "TOUR", "ツアー", "B.LEAGUE", "大相撲", "競技大会",
)
SPORT_WORDS = ("B.LEAGUE", "リーグ戦", " vs ", "大相撲", "競技大会", "パラ競技大会")
CONCERT_WORDS = ("TOUR", "ツアー", "LIVE", "ライブ", "コンサート", "Anniversary")

@dataclass(frozen=True)
class Event:
    title: str
    start_date: str
    end_date: str
    venue: str
    prefecture: str
    category: str
    source: str
    official_url: str
    decision: str = "hold"
    decision_reason: str = "未判定"


def classify_event(event: Event) -> Event:
    title = event.title.strip()
    matched = next((word for word in EXCLUDE_WORDS if word in title), None)
    if matched:
        return replace(event, decision="exclude", decision_reason=f"一般向けでない可能性が高い語: {matched}")
    matched = next((word for word in HOLD_WORDS if word in title), None)
    if matched:
        return replace(event, decision="hold", decision_reason=f"規模・一般的なお出かけ価値を名前だけでは判断しにくい: {matched}")
    if event.category in DISPLAY_CATEGORIES:
        return replace(event, decision="display", decision_reason=f"目的対象ジャンル: {event.category}")
    matched = next((word for word in DISPLAY_WORDS if word.casefold() in title.casefold()), None)
    if matched:
        return replace(event, decision="display", decision_reason=f"大型・一般向けイベントを示す語: {matched}")
    return replace(event, decision="hold", decision_reason="名前とジャンルだけでは大型・一般向けか判断できない")


def month_keys(start: date, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


def month_keys_dash(start: date, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.4)"})
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def fetch_json(url: str) -> dict:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.4)"})
    r.raise_for_status()
    return r.json()


def _sky_date_parts(text: str):
    m = SKY_DATE_RE.search(text)
    if not m:
        return None
    return f"{m['sy']}-{m['sm']}-{m['sd']}", f"{m['ey']}-{m['em']}-{m['ed']}"


def _sky_find_card(date_node):
    node = getattr(date_node, "parent", None)
    for _ in range(8):
        if node is None:
            break
        text = node.get_text(" ", strip=True)
        heading = node.find(["h2", "h3", "h4"])
        if heading and "会場" in text and any(c in text for c in CATEGORIES):
            return node
        if len(text) > 5000:
            break
        node = getattr(node, "parent", None)
    return None


def _sky_extract_from_card(card, source_url: str):
    full_text = card.get_text(" ", strip=True)
    parts = _sky_date_parts(full_text)
    heading = card.find(["h2", "h3", "h4"])
    if not parts or not heading:
        return None
    title = heading.get_text(" ", strip=True)
    category = next((c for c in CATEGORIES if c in full_text), None)
    if not title or not category:
        return None
    venue = None
    for tag in card.find_all(["p", "div", "span", "li"]):
        t = tag.get_text(" ", strip=True)
        if t.startswith("会場"):
            venue = t[2:].strip()
            break
    if not venue:
        m = re.search(r"会場\s*([^|]+?)(?=(?:イベント公式HPへ|$))", full_text)
        if m:
            venue = m.group(1).strip()
    if not venue:
        return None
    official = source_url
    for a in card.find_all("a", href=True):
        if "イベント公式HPへ" in a.get_text(" ", strip=True):
            official = urljoin(SKY_BASE, a["href"])
            break
    start, end = parts
    return classify_event(Event(title, start, end, venue, "愛知県", category, "Aichi Sky Expo", official))


def _sky_fallback_parse(soup: BeautifulSoup, source_url: str):
    lines = [x.strip() for x in soup.stripped_strings if x.strip()]
    events = []
    for i, line in enumerate(lines):
        parts = _sky_date_parts(line)
        if not parts:
            continue
        start, end = parts
        window = lines[i + 1:i + 14]
        title = category = venue = None
        for s in window:
            if s in CATEGORIES and category is None:
                category = s
                continue
            if s.startswith("会場") and venue is None:
                venue = s[2:].strip()
                continue
            if title is None and s not in CATEGORIES and not s.startswith("会場") and s != "イベント公式HPへ" and not _sky_date_parts(s):
                title = s
        if title and category and venue:
            events.append(classify_event(Event(title, start, end, venue, "愛知県", category, "Aichi Sky Expo", source_url)))
    return events


def parse_events(page_html: str, source_url: str):
    soup = BeautifulSoup(page_html, "html.parser")
    events = []
    for text_node in soup.find_all(string=lambda s: bool(s and SKY_DATE_RE.search(s))):
        card = _sky_find_card(text_node)
        if card is None:
            continue
        event = _sky_extract_from_card(card, source_url)
        if event:
            events.append(event)
    if not events:
        events = _sky_fallback_parse(soup, source_url)
    unique = {(e.title, e.start_date, e.end_date, e.venue): e for e in events}
    return list(unique.values())


def _parse_ig_dates(date_text: str, month_key: str):
    matches = list(JP_DATE_RE.finditer(date_text))
    if not matches:
        return None
    current_year = int(matches[0].group("year") or month_key[:4])
    dates = []
    for m in matches:
        if m.group("year"):
            current_year = int(m.group("year"))
        dates.append(f"{current_year:04d}-{int(m.group('month')):02d}-{int(m.group('day')):02d}")
    return dates[0], dates[-1]


def _ig_category(title: str) -> str:
    folded = title.casefold()
    if any(word.casefold() in folded for word in SPORT_WORDS):
        return "スポーツ"
    if any(word.casefold() in folded for word in CONCERT_WORDS):
        return "コンサート・ショー"
    return "その他"


def parse_ig_api(payload: dict, month_key: str):
    items = payload.get("data", []) if isinstance(payload, dict) else []
    events = []
    for item in items:
        title = str(item.get("title") or "").strip()
        date_text = str(item.get("date") or "").strip()
        event_id = str(item.get("link") or item.get("id") or "").strip()
        parts = _parse_ig_dates(date_text, month_key)
        if not title or not parts:
            continue
        start, end = parts
        official = IG_EVENT_URL.format(event_id=event_id) if event_id else IG_BASE + "/events/"
        events.append(classify_event(Event(title, start, end, "IGアリーナ", "愛知県", _ig_category(title), "IGアリーナ", official)))
    unique = {(e.title, e.start_date, e.end_date, e.venue): e for e in events}
    return list(unique.values())


def build_site(events: list[Event]):
    SITE_DIR.mkdir(exist_ok=True)
    events = sorted(events, key=lambda e: (e.start_date, e.title))
    (SITE_DIR / "events.json").write_text(json.dumps([asdict(e) for e in events], ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {
        "display": sum(e.decision == "display" for e in events),
        "hold": sum(e.decision == "hold" for e in events),
        "exclude": sum(e.decision == "exclude" for e in events),
    }
    meta = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "source_count": len({e.source for e in events}),
        "event_count": len(events),
        "decision_counts": counts,
    }
    (SITE_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    today = date.today()
    collected = []
    print("SOURCE Aichi Sky Expo")
    for ym in month_keys(today, 6):
        url = SKY_LIST_URL.format(ym=ym)
        print("FETCH", url)
        found = parse_events(fetch_html(url), url)
        print("  ->", len(found), "events")
        collected.extend(found)
    print("SOURCE IG Arena")
    for ym in month_keys_dash(today, 6):
        url = IG_API_URL.format(ym=ym)
        print("FETCH", url)
        found = parse_ig_api(fetch_json(url), ym)
        print("  ->", len(found), "events")
        collected.extend(found)
    today_iso = today.isoformat()
    collected = [e for e in collected if e.end_date >= today_iso]
    unique = {(e.title, e.start_date, e.end_date, e.venue): e for e in collected}
    events = list(unique.values())
    if not events:
        raise RuntimeError("0件でした。サイト構造変更の可能性があります。")
    build_site(events)
    counts = {
        "display": sum(e.decision == "display" for e in events),
        "hold": sum(e.decision == "hold" for e in events),
        "exclude": sum(e.decision == "exclude" for e in events),
    }
    print("DONE", len(events), counts, "sources", len({e.source for e in events}))


if __name__ == "__main__":
    main()
