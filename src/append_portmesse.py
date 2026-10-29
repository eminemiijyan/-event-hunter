from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

BASE = "https://portmesse.com"
MONTH_URL = BASE + "/events?month={month}&yr={year}&time=month"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

DATE_RE = re.compile(
    r"(?P<sy>\d{4})年(?P<sm>\d{1,2})月(?P<sd>\d{1,2})日"
    r"(?:\s*[–—-]\s*(?P<ey>\d{4})年(?P<em>\d{1,2})月(?P<ed>\d{1,2})日)?"
)

SKIP_WORDS = (
    "就職", "就活", "インターンシップ", "キャリア発見", "採用", "企業説明会", "転職",
    "プライベート", "関係者限定", "一般入場不可", "一般非公開",
)


def fetch_html(url: str) -> str:
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.8)"},
    )
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def month_keys(start, count: int = 3):
    y, m = start.year, start.month
    for _ in range(count):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def parse_dates(text: str) -> tuple[str, str] | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    start = f"{int(m['sy']):04d}-{int(m['sm']):02d}-{int(m['sd']):02d}"
    if m.group("ey"):
        end = f"{int(m['ey']):04d}-{int(m['em']):02d}-{int(m['ed']):02d}"
    else:
        end = start
    return start, end


def _external_link(article, source_url: str) -> str:
    for a in article.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href.startswith(("http://", "https://")):
            continue
        host = (urlparse(href).hostname or "").lower()
        if host and host not in {"portmesse.com", "www.portmesse.com"}:
            return href
    return source_url


def parse_month(page_html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    events = []

    for article in soup.select("article.calendar-event"):
        title_node = article.select_one("h3.event-title")
        if not title_node:
            continue
        title = title_node.get_text(" ", strip=True)
        if not title or any(word in title for word in SKIP_WORDS):
            continue

        full_text = " ".join(article.stripped_strings)
        dates = parse_dates(full_text)
        if not dates:
            continue
        start, end = dates

        vm = re.search(r"会場：\s*(.*?)\s*お問合せ：", full_text)
        venue_name = vm.group(1).strip() if vm else ""
        venue = "ポートメッセなごや" + (f" {venue_name}" if venue_name else "")

        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "venue": venue,
            "prefecture": "愛知県",
            "category": "展示会",
            "source": "ポートメッセなごや",
            "official_url": _external_link(article, source_url),
            "decision": "display",
            "decision_reason": "ポートメッセなごや公式掲載イベント",
        })

    unique = {}
    for event in events:
        key = (event["title"], event["start_date"], event["end_date"], event["venue"])
        unique[key] = event
    return list(unique.values())


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    found = []
    for year, month in month_keys(today, 3):
        url = MONTH_URL.format(year=year, month=month)
        month_events = parse_month(fetch_html(url), url)
        print("PORTMESSE", f"{year:04d}-{month:02d}", len(month_events))
        found.extend(month_events)

    found = [e for e in found if e["end_date"] >= today.isoformat()]
    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in merged),
        "hold": sum(e.get("decision") == "hold" for e in merged),
        "exclude": sum(e.get("decision") == "exclude" for e in merged),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PORTMESSE added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
