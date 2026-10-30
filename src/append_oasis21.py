from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.sakaepark.co.jp"
EVENTS_URL = BASE + "/events/?ym={year:04d}-{month:02d}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

# Event Hunter向けの「わざわざ出かける候補」だけを残す。
MAJOR_WORDS = (
    "フェス",
    "fes",
    "フェスティバル",
    "マルシェ",
    "マーケット",
    "market",
    "祭",
    "まつり",
    "音楽広場",
    "ライブサイト",
    "鉄道の日",
    "ケーブルフェスタ",
    "スポnago",
    "expo",
    "夜市",
    "パレード",
)

SMALL_WORDS = (
    "朝市",
    "アトリエ",
    "ワークショップ",
    "体験イベント",
    "街角コンサート",
    "サックス侍",
)

DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")


def month_keys(start: date, count: int = 6):
    year, month = start.year, start.month
    for _ in range(count):
        yield year, month
        month += 1
        if month == 13:
            year += 1
            month = 1


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
            print(f"OASIS21 retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def is_major(title: str) -> bool:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    if any(word in normalized for word in SMALL_WORDS):
        return False
    return any(word in normalized for word in MAJOR_WORDS)


def parse_dates(text: str) -> tuple[str, str] | None:
    matches = DATE_RE.findall(text)
    if not matches:
        return None
    parsed = [date(int(y), int(m), int(d)) for y, m, d in matches]
    return parsed[0].isoformat(), parsed[-1].isoformat()


def category_for(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    if any(word in normalized for word in ("マルシェ", "マーケット", "market", "夜市")):
        return "グルメ・マーケット"
    if any(word in normalized for word in ("音楽", "ライブ", "コンサート")):
        return "コンサート・ショー"
    if any(word in normalized for word in ("スポ", "スポーツ")):
        return "スポーツ"
    return "その他"


def parse_month(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    seen: set[tuple[str, str]] = set()

    for item in soup.select("#event_calendar .box_days li.news_item"):
        anchor = item.select_one("a.has_arrow[href]")
        date_node = item.select_one(".date")
        venue_node = item.select_one(".news_category")
        title_node = item.select_one("strong span")
        if not anchor or not date_node or not title_node:
            continue

        title = title_node.get_text(" ", strip=True)
        if not is_major(title):
            continue

        dates = parse_dates(date_node.get_text(" ", strip=True))
        if not dates:
            continue
        start_date, end_date = dates

        venue_area = venue_node.get_text(" ", strip=True) if venue_node else ""
        venue = f"オアシス21・{venue_area}" if venue_area and "オアシス" not in venue_area else "オアシス21"
        url = anchor.get("href", "").strip()
        if not url:
            continue

        key = (_norm(title), start_date)
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "venue": venue,
            "category": category_for(title),
            "official_url": url,
        })

    return out


def _is_duplicate(existing: dict, candidate: dict) -> bool:
    if existing.get("start_date") != candidate.get("start_date"):
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

    found: dict[tuple[str, str], dict] = {}
    successful_months = 0
    total_list_items = 0

    for year, month in month_keys(today, 6):
        url = EVENTS_URL.format(year=year, month=month)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"OASIS21 month skipped: {type(exc).__name__} {year:04d}-{month:02d}")
            continue

        successful_months += 1
        soup = BeautifulSoup(html, "html.parser")
        total_list_items += len(soup.select("#event_calendar .box_days li.news_item"))
        month_items = parse_month(html)
        print("OASIS21", f"{year:04d}-{month:02d}", "major", len(month_items))
        for item in month_items:
            if item["end_date"] >= today.isoformat():
                found[(_norm(item["title"]), item["start_date"])] = item

    if successful_months == 0:
        print("OASIS21 skipped: source unavailable after retries")
        return
    if total_list_items == 0:
        raise RuntimeError("オアシス21のイベント一覧を取得できませんでした。サイト構造変更の可能性があります。")

    before = len(events)
    for item in sorted(found.values(), key=lambda e: (e["start_date"], e["title"])):
        if any(_is_duplicate(existing, item) for existing in events):
            continue
        events.append({
            "title": item["title"],
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "venue": item["venue"],
            "prefecture": "愛知県",
            "category": item["category"],
            "source": "オアシス21",
            "official_url": item["official_url"],
            "decision": "display",
            "decision_reason": "オアシス21公式イベント一覧の大型・街イベント候補",
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

    print("OASIS21 found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
