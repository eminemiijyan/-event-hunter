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

BASE = "https://www.zepp.co.jp"
SCHEDULE_URL = BASE + "/hall/nagoya/schedule/?_y={year:04d}&_m={month}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"


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
            print(f"ZEPP_NAGOYA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def display_title(performer: str, event_title: str) -> str:
    performer = performer.strip()
    event_title = event_title.strip()
    if not performer:
        return event_title
    if not event_title:
        return performer
    p = _norm(performer)
    t = _norm(event_title)
    if p and p in t:
        return event_title
    return f"{performer} — {event_title}"


def parse_month(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    seen_urls: set[str] = set()

    for anchor in soup.select('a.sch-content[href*="/hall/nagoya/schedule/single/"]'):
        url = anchor.get("href", "").strip()
        if not url or url in seen_urls:
            continue

        year_node = anchor.select_one(".sch-content-date__year")
        month_day_node = anchor.select_one(".sch-content-date__month")
        performer_node = anchor.select_one(".sch-content-text__performer")
        title_node = anchor.select_one(".sch-content-text__ttl")
        if not year_node or not month_day_node:
            continue

        try:
            year = int(year_node.get_text(" ", strip=True))
            month_str, day_str = month_day_node.get_text(" ", strip=True).split(".", 1)
            event_date = date(year, int(month_str), int(day_str)).isoformat()
        except (ValueError, TypeError):
            continue

        performer = performer_node.get_text(" ", strip=True) if performer_node else ""
        event_title = title_node.get_text(" ", strip=True) if title_node else ""
        title = display_title(performer, event_title)
        if not title:
            continue

        out.append({
            "title": title,
            "performer": performer,
            "raw_title": event_title,
            "start_date": event_date,
            "end_date": event_date,
            "official_url": url,
        })
        seen_urls.add(url)

    return out


def _same_zepp_event(existing: dict, candidate: dict) -> bool:
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    venue = _norm(existing.get("venue", ""))
    if "zeppnagoya" not in venue:
        return False

    existing_title = _norm(existing.get("title", ""))
    if not existing_title:
        return False

    candidate_parts = [
        _norm(candidate.get("performer", "")),
        _norm(candidate.get("raw_title", "")),
        _norm(candidate.get("title", "")),
    ]
    for part in candidate_parts:
        if part and (part in existing_title or existing_title in part):
            return True
    return False


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    found: dict[str, dict] = {}
    successful_months = 0
    total_cards = 0

    for year, month in month_keys(today, 6):
        url = SCHEDULE_URL.format(year=year, month=month)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"ZEPP_NAGOYA month skipped: {type(exc).__name__} {year:04d}-{month:02d}")
            continue

        successful_months += 1
        month_items = parse_month(html)
        total_cards += len(month_items)
        print("ZEPP_NAGOYA", f"{year:04d}-{month:02d}", "events", len(month_items))
        for item in month_items:
            if item["end_date"] >= today.isoformat():
                found[item["official_url"]] = item

    if successful_months == 0:
        print("ZEPP_NAGOYA skipped: source unavailable after retries")
        return
    if total_cards == 0:
        raise RuntimeError("Zepp Nagoyaの公演一覧を取得できませんでした。サイト構造変更の可能性があります。")

    before = len(events)
    for item in sorted(found.values(), key=lambda e: (e["start_date"], e["title"])):
        if any(_same_zepp_event(existing, item) for existing in events):
            continue
        events.append({
            "title": item["title"],
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "venue": "Zepp Nagoya",
            "prefecture": "愛知県",
            "category": "コンサート・ショー",
            "source": "Zepp Nagoya",
            "official_url": item["official_url"],
            "decision": "display",
            "decision_reason": "Zepp Nagoya公式スケジュール掲載公演",
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

    print("ZEPP_NAGOYA found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
