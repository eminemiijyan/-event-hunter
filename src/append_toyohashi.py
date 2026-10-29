from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

BASE = "https://www.honokuni.or.jp"
LIST_URL = BASE + "/toyohashi/event-info/?Mode=month&ym={ym}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_RE = re.compile(
    r"(?P<sy>20\d{2})年(?P<sm>\d{1,2})月(?P<sd>\d{1,2})日(?:\([^)]*\))?\s*[～~〜-]\s*"
    r"(?P<ey>20\d{2})年(?P<em>\d{1,2})月(?P<ed>\d{1,2})日"
)

MAJOR_WORDS = (
    "まつり", "祭り", "祭典", "フェス", "フェスタ", "festival", "フェア",
    "花火", "大名行列", "イルミネーション", "ライトアップ", "ポケモン",
    "のんほいパーク", "子育て応援", "スタンプラリー",
)
SKIP_WORDS = (
    "中止", "定期演奏会", "写真展", "ミニチュアカー展", "講座", "教室", "募集",
)


def month_keys(start, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m == 13:
            y += 1
            m = 1


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
            print(f"TOYOHASHI retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _is_major(title: str) -> bool:
    if any(word in title for word in SKIP_WORDS):
        return False
    folded = title.casefold()
    return any(word.casefold() in folded for word in MAJOR_WORDS)


def _dates(text: str) -> tuple[str, str] | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    return (
        f"{int(m['sy']):04d}-{int(m['sm']):02d}-{int(m['sd']):02d}",
        f"{int(m['ey']):04d}-{int(m['em']):02d}-{int(m['ed']):02d}",
    )


def category_for(title: str) -> str:
    folded = title.casefold()
    if any(word.casefold() in folded for word in ("まつり", "祭り", "祭典", "フェス", "フェスタ", "festival", "花火", "イルミネーション", "ライトアップ", "大名行列")):
        return "祭り・季節"
    if "ポケモン" in title:
        return "ゲーム・アニメ"
    return "その他"


def parse_month(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    events = []
    for li in soup.find_all("li"):
        title_node = li.find("h4")
        note = li.select_one("._my_photo_note")
        link = li.find("a", href=True)
        if not title_node or not note or not link:
            continue
        title = title_node.get_text(" ", strip=True)
        href = link.get("href", "")
        if "Mode=detail" not in href or not _is_major(title):
            continue
        dates = _dates(note.get_text(" ", strip=True))
        if not dates:
            continue
        start, end = dates
        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "venue": "豊橋市内",
            "prefecture": "愛知県",
            "category": category_for(title),
            "source": "ええじゃないか豊橋",
            "official_url": urljoin(BASE + "/toyohashi/event-info/", href),
            "decision": "display",
            "decision_reason": "豊橋観光公式掲載の主要・家族向けイベント",
        })
    unique = {(e["title"], e["start_date"], e["end_date"]): e for e in events}
    return list(unique.values())


def parse_detail_venue(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    for label in soup.find_all(["th", "dt", "td", "div", "span"]):
        if label.get_text(" ", strip=True) != "開催場所":
            continue
        if label.name == "th":
            value = label.find_next_sibling("td")
        elif label.name == "dt":
            value = label.find_next_sibling("dd")
        else:
            value = label.find_next_sibling()
        if value:
            venue = value.get_text(" ", strip=True)
            if venue:
                return venue
    text = " ".join(soup.stripped_strings)
    m = re.search(r"開催場所\s*(.*?)\s*(?=交通機関|問合せ先|お問い合わせ|料金|所在地|この祭について)", text)
    if m:
        venue = m.group(1).strip()
        if venue:
            return venue
    return None


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    found = []
    successful_months = 0
    for ym in month_keys(today, 6):
        url = LIST_URL.format(ym=ym)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"TOYOHASHI month skipped: {type(exc).__name__} {ym}")
            continue
        successful_months += 1
        month_events = parse_month(html)
        print("TOYOHASHI", ym, "candidates", len(month_events))
        found.extend(month_events)

    if successful_months == 0:
        print("TOYOHASHI skipped: source unavailable after retries")
        return

    unique = {(e["title"], e["start_date"], e["end_date"]): e for e in found}
    found = [e for e in unique.values() if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("豊橋観光公式の主要イベントを取得できませんでした。サイト構造変更の可能性があります。")

    failed_details = 0
    for event in found:
        try:
            detail_html = fetch_html(event["official_url"])
        except requests.RequestException as exc:
            failed_details += 1
            print(f"TOYOHASHI detail skipped: {type(exc).__name__} {event['official_url']}")
            continue
        venue = parse_detail_venue(detail_html)
        if venue:
            event["venue"] = venue

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
    print("TOYOHASHI found", len(found), "added", len(merged) - before, "failed_details", failed_details)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
