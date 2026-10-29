from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.aichiskyexpo.com"
LIST_URL = BASE + "/ase-event/?ym={ym}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

DATE_RE = re.compile(
    r"(?P<sy>\d{4})\.(?P<sm>\d{2})\.(?P<sd>\d{2})"
    r"\s*\([^)]+\)\s*-\s*"
    r"(?P<ey>\d{4})\.(?P<em>\d{2})\.(?P<ed>\d{2})"
    r"\s*\([^)]+\)"
)

CATEGORIES = {
    "その他",
    "ゲーム",
    "コンサート・ショー",
    "スポーツ",
    "セミナー・シンポジウム",
    "展示会",
}

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


def month_keys(start: date, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


def fetch_html(url: str) -> str:
    r = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; EventHunterPersonal/0.2; "
                "+https://github.com/)"
            )
        },
    )
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def _date_parts(text: str):
    m = DATE_RE.search(text)
    if not m:
        return None
    start = f"{m['sy']}-{m['sm']}-{m['sd']}"
    end = f"{m['ey']}-{m['em']}-{m['ed']}"
    return start, end


def _find_card(date_node):
    node = getattr(date_node, "parent", None)
    for _ in range(8):
        if node is None:
            break
        text = node.get_text(" ", strip=True)
        heading = node.find(["h2", "h3", "h4"])
        has_venue = "会場" in text
        has_category = any(c in text for c in CATEGORIES)
        if heading and has_venue and has_category:
            return node
        if len(text) > 5000:
            break
        node = getattr(node, "parent", None)
    return None


def _extract_from_card(card, source_url: str):
    full_text = card.get_text(" ", strip=True)
    parts = _date_parts(full_text)
    heading = card.find(["h2", "h3", "h4"])
    if not parts or not heading:
        return None

    title = heading.get_text(" ", strip=True)
    if not title:
        return None

    category = next((c for c in CATEGORIES if c in full_text), None)
    if not category:
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
        label = a.get_text(" ", strip=True)
        href = urljoin(BASE, a["href"])
        if "イベント公式HPへ" in label:
            official = href
            break

    start, end = parts
    return Event(
        title=title,
        start_date=start,
        end_date=end,
        venue=venue,
        prefecture="愛知県",
        category=category,
        source="Aichi Sky Expo",
        official_url=official,
    )


def _fallback_parse(soup: BeautifulSoup, source_url: str):
    lines = [x.strip() for x in soup.stripped_strings if x.strip()]
    events = []
    for i, line in enumerate(lines):
        parts = _date_parts(line)
        if not parts:
            continue
        start, end = parts
        window = lines[i + 1:i + 14]
        title = None
        category = None
        venue = None
        for s in window:
            if s in CATEGORIES and category is None:
                category = s
                continue
            if s.startswith("会場") and venue is None:
                venue = s[2:].strip()
                continue
            if (
                title is None
                and s not in CATEGORIES
                and not s.startswith("会場")
                and s != "イベント公式HPへ"
                and not _date_parts(s)
            ):
                title = s
        if title and category and venue:
            events.append(Event(
                title=title,
                start_date=start,
                end_date=end,
                venue=venue,
                prefecture="愛知県",
                category=category,
                source="Aichi Sky Expo",
                official_url=source_url,
            ))
    return events


def parse_events(page_html: str, source_url: str):
    soup = BeautifulSoup(page_html, "html.parser")
    events = []

    for text_node in soup.find_all(string=lambda s: bool(s and DATE_RE.search(s))):
        card = _find_card(text_node)
        if card is None:
            continue
        event = _extract_from_card(card, source_url)
        if event:
            events.append(event)

    if not events:
        events = _fallback_parse(soup, source_url)

    unique = {}
    for e in events:
        unique[(e.title, e.start_date, e.end_date, e.venue)] = e
    return list(unique.values())


def build_site(events: list[Event]):
    SITE_DIR.mkdir(exist_ok=True)
    events = sorted(events, key=lambda e: (e.start_date, e.title))

    payload = [asdict(e) for e in events]
    (SITE_DIR / "events.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta = {
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "source_count": 1,
        "event_count": len(events),
    }
    (SITE_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    today = date.today()
    collected = []

    for ym in month_keys(today, 6):
        url = LIST_URL.format(ym=ym)
        print("FETCH", url)
        page_html = fetch_html(url)
        found = parse_events(page_html, url)
        print("  ->", len(found), "events")
        collected.extend(found)

    today_iso = today.isoformat()
    collected = [e for e in collected if e.end_date >= today_iso]

    unique = {}
    for e in collected:
        unique[(e.title, e.start_date, e.end_date, e.venue)] = e

    events = list(unique.values())
    if not events:
        raise RuntimeError("0件でした。サイト構造変更の可能性があります。")

    build_site(events)
    print("DONE", len(events))


if __name__ == "__main__":
    main()
