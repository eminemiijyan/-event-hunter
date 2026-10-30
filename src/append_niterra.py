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

BASE = "https://nagoya-shimin.hall-info.jp"
HOME_URL = BASE + "/kaikan/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

MONTH_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月")
DAY_RE = re.compile(r"(\d{1,2})日")
TIME_ONLY_RE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩\s:：0-9～〜\-・]+$")

IGNORE_TITLES = {"利用あり", "施設点検日", "ホール点検日", "休館日"}


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                url,
                timeout=(10, 45),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
                },
            )
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            print(f"NITERRA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def discover_month_pages(home_html: str, today: date) -> list[tuple[int, int, str]]:
    soup = BeautifulSoup(home_html, "html.parser")
    out: dict[tuple[int, int], str] = {}
    current_key = today.year * 12 + today.month
    for a in soup.select('a[href*="/kaikan/event/"]'):
        text = a.get_text(" ", strip=True)
        m = MONTH_RE.search(text)
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        key = year * 12 + month
        if key < current_key:
            continue
        href = a.get("href", "").strip()
        if href:
            out[(year, month)] = urljoin(BASE, href)
    return [(y, m, out[(y, m)]) for y, m in sorted(out)]


def _page_year_month(soup: BeautifulSoup) -> tuple[int, int] | None:
    for node in soup.find_all(["h1", "h2"]):
        m = MONTH_RE.search(node.get_text(" ", strip=True))
        if m:
            return int(m.group(1)), int(m.group(2))
    m = MONTH_RE.search(soup.get_text(" ", strip=True))
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _public_title(text: str) -> bool:
    t = " ".join(text.split()).strip()
    if not t or t in IGNORE_TITLES:
        return False
    if "関係者" in t and "のみ" in t:
        return False
    return True


def parse_month(page_html: str, page_url: str = "") -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    ym = _page_year_month(soup)
    if not ym:
        return []
    year, month = ym
    out: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    hall_specs = (
        ("フォレストホール", "Niterra日本特殊陶業市民会館 フォレストホール"),
        ("ビレッジホール", "Niterra日本特殊陶業市民会館 ビレッジホール"),
    )

    for h2 in soup.find_all("h2"):
        heading = h2.get_text(" ", strip=True)
        venue = None
        for key, label in hall_specs:
            if key in heading:
                venue = label
                break
        if not venue:
            continue

        table = h2.find_next("table")
        if not table:
            continue

        previous: dict | None = None
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            date_text = cells[0].get_text(" ", strip=True)
            dm = DAY_RE.search(date_text)
            if not dm:
                continue
            try:
                event_date = date(year, month, int(dm.group(1))).isoformat()
            except ValueError:
                continue

            row_text = " ".join(row.get_text(" ", strip=True).split())
            title_text = cells[1].get_text(" ", strip=True) if len(cells) >= 2 else ""
            title_text = " ".join(title_text.split()).strip()

            if previous and (not title_text or TIME_ONLY_RE.fullmatch(title_text)):
                previous["end_date"] = event_date
                continue
            if not _public_title(title_text):
                previous = None
                continue
            if "関係者" in row_text and "のみ" in row_text:
                previous = None
                continue

            item = {
                "title": title_text,
                "start_date": event_date,
                "end_date": event_date,
                "venue": venue,
                "official_url": page_url or HOME_URL,
            }
            key = (_norm(title_text), event_date, venue)
            if key in seen:
                previous = None
                continue
            seen.add(key)
            out.append(item)
            previous = item

    return out


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    existing_venue = existing.get("venue", "")
    if "Niterra" not in existing_venue and "日本特殊陶業市民会館" not in existing_venue:
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        home_html = fetch_html(HOME_URL)
    except requests.RequestException as exc:
        print("NITERRA skipped: homepage unavailable", type(exc).__name__)
        return

    pages = discover_month_pages(home_html, today)
    if not pages:
        raise RuntimeError("Niterra日本特殊陶業市民会館の月別催事ページを発見できませんでした。")

    found: list[dict] = []
    successful = 0
    for year, month, url in pages:
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"NITERRA month skipped: {type(exc).__name__} {year:04d}-{month:02d}")
            continue
        successful += 1
        items = parse_month(html, url)
        print("NITERRA", f"{year:04d}-{month:02d}", "public", len(items))
        found.extend(item for item in items if item["end_date"] >= today.isoformat())

    if successful == 0:
        print("NITERRA skipped: monthly pages unavailable after retries")
        return
    if not found:
        raise RuntimeError("Niterra日本特殊陶業市民会館の公開催事を取得できませんでした。サイト構造変更の可能性があります。")

    before = len(events)
    for item in sorted(found, key=lambda e: (e["start_date"], e["title"])):
        if any(_same_event(existing, item) for existing in events):
            continue
        events.append({
            "title": item["title"],
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "venue": item["venue"],
            "prefecture": "愛知県",
            "category": "コンサート・ショー",
            "source": "Niterra日本特殊陶業市民会館",
            "official_url": item["official_url"],
            "decision": "display",
            "decision_reason": "Niterra日本特殊陶業市民会館公式催事案内の一般公開公演",
        })

    events = sorted(events, key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in events),
        "hold": sum(e.get("decision") == "hold" for e in events),
        "exclude": sum(e.get("decision") == "exclude" for e in events),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("NITERRA found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
