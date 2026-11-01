from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.town.anpachi.lg.jp"
INDEX_URL = BASE + "/category/5-0-0-0-0-0-0-0-0-0.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "安八町 観光・イベント"

DATE_TOKEN_RE = re.compile(r"(?:(?:令和\s*(\d+)年)|(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日")
EVENT_PATH_RE = re.compile(r"/000000\d+\.html$")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 40), headers={
                "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                "Accept-Language": "ja-JP,ja;q=0.9",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"ANPACHI_EVENTS retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def extract_event_links(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[tuple[str, str]] = []
    active = False
    for node in soup.find_all(["h2", "h3", "a"]):
        if node.name in ("h2", "h3"):
            heading = _clean(node.get_text(" ", strip=True))
            if heading == "イベント情報":
                active = True
                continue
            if active and heading not in ("イベント情報",):
                break
            continue
        if not active:
            continue
        title = _clean(node.get_text(" ", strip=True))
        href = node.get("href", "").strip()
        if not title or not EVENT_PATH_RE.search(href):
            continue
        pair = (title, urljoin(BASE, href))
        if pair not in links:
            links.append(pair)
    return links


def parse_dates(text: str) -> tuple[str, str] | None:
    values: list[date] = []
    current_year: int | None = None
    current_month: int | None = None
    for match in DATE_TOKEN_RE.finditer(_clean(text)):
        era_year, western_year, month, day = match.groups()
        if era_year:
            current_year = 2018 + int(era_year)
        elif western_year:
            current_year = int(western_year)
        if month:
            current_month = int(month)
        if current_year is None or current_month is None:
            continue
        try:
            values.append(date(current_year, current_month, int(day)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def _extract_labeled_text(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    for node in soup.find_all(["p", "div", "li", "td", "th", "h3", "h4"]):
        text = _clean(node.get_text(" ", strip=True))
        if not text:
            continue
        for label in labels:
            if text.startswith(label):
                value = _clean(re.sub(r"^" + re.escape(label) + r"\s*[:：]?\s*", "", text, count=1))
                if value:
                    return value
                sibling = node.find_next_sibling()
                if sibling:
                    return _clean(sibling.get_text(" ", strip=True))
    return ""


def category_for(title: str) -> str:
    if any(word in title for word in ("絵本", "企画展", "展示", "展覧")):
        return "展示会"
    if any(word in title for word in ("祭", "まつり", "水まつり")):
        return "祭り・季節"
    if any(word in title for word in ("スポーツ", "大会", "レクリエーション")):
        return "スポーツ"
    if any(word in title for word in ("トークショー", "コンサート", "公演")):
        return "コンサート・ショー"
    return "イベント"


def parse_detail(html: str, fallback_title: str, url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    title = fallback_title
    h1 = soup.find("h1")
    if h1:
        candidate = _clean(h1.get_text(" ", strip=True))
        if candidate:
            title = candidate

    date_text = _extract_labeled_text(soup, ("開催日時", "日時", "開催日", "開催期間"))
    if not date_text:
        body = _clean(" ".join(soup.stripped_strings))
        date_match = re.search(r"(?:開催日時|日時|開催日|開催期間)\s*[:：]?\s*(.{0,120})", body)
        date_text = date_match.group(1) if date_match else ""
    dates = parse_dates(date_text)
    if not dates:
        return None

    venue = _extract_labeled_text(soup, ("場所", "会場", "開催場所")) or "安八町内"
    return {
        "title": title,
        "start_date": dates[0],
        "end_date": dates[1],
        "venue": venue,
        "prefecture": "岐阜県",
        "category": category_for(title),
        "source": SOURCE,
        "official_url": url,
        "decision": "display",
        "decision_reason": "安八町公式の観光・イベント情報に掲載",
    }


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a, b = _norm(existing.get("title", "")), _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    events_path, meta_path = SITE_DIR / "events.json", SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        index_html = fetch_html(INDEX_URL)
    except requests.RequestException as exc:
        print("ANPACHI_EVENTS skipped: official index unavailable", type(exc).__name__)
        return

    links = extract_event_links(index_html)
    found: list[dict] = []
    failed = 0
    for title, url in links[:12]:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException as exc:
            failed += 1
            print("ANPACHI_EVENTS detail skipped", type(exc).__name__, url)
            continue
        event = parse_detail(html, title, url)
        if event and event["end_date"] >= now.date().isoformat():
            found.append(event)

    before = len(events)
    for item in found:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda event: (event.get("start_date", ""), event.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {key: sum(event.get("decision") == key for event in events) for key in ("display", "hold", "exclude")}
    meta.update({"updated_at": now.isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ANPACHI_EVENTS links", len(links), "future", len(found), "added", len(events) - before, "failed_details", failed)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
