from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://dmo.hana-meiwa.jp"
LIST_URL = f"{BASE}/category/categoy-event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
TARGET_WORDS = ("祭", "まつり", "フェス", "観月会", "ランタン", "花火", "ライトアップ", "イルミ", "斎王")
EXCLUDE_WORDS = ("満月イベント", "満月屋台", "月の市", "ワークショップ", "収穫体験", "講座", "セミナー", "募集")
POSTED_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日\s*/")
META_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日\s*/\s*最終更新日時\s*[:：]\s*20\d{2}年\d{1,2}月\d{1,2}日")
GREG_JP_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
MD_RE = re.compile(r"(?<!\d)(\d{1,2})月\s*(\d{1,2})日")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 45), headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)", "Accept-Language": "ja-JP,ja;q=0.9"})
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"MEIWA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _clean_title(title: str) -> str:
    title = re.sub(r"^(?:[【〖][^】〗]+[】〗]\s*)+", "", title).strip()
    title = re.sub(r"^(?:プレスリリース\s*)+", "", title).strip()
    return title


def _is_target(title: str) -> bool:
    return not any(w in title for w in EXCLUDE_WORDS) and any(w in title for w in TARGET_WORDS)


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[str] = set()
    for heading in soup.find_all(["h1", "h2"]):
        a = heading.find("a", href=True)
        if not a:
            continue
        title = _clean_title(" ".join(a.get_text(" ", strip=True).split()))
        if not title or not _is_target(title):
            continue
        url = urljoin(BASE, a.get("href", "").strip())
        if urlparse(url).netloc != "dmo.hana-meiwa.jp" or url in seen:
            continue
        seen.add(url)
        out.append({"title": title, "url": url})
    return out


def _date_range(text: str) -> tuple[date, date] | None:
    metadata = META_RE.search(text)
    posted = metadata or POSTED_RE.search(text)
    posted_year = int(posted.group(1)) if posted else datetime.now(ZoneInfo("Asia/Tokyo")).year
    posted_month = int(posted.group(2)) if posted else 1
    scrubbed = META_RE.sub("", text)
    scrubbed = POSTED_RE.sub("", scrubbed)
    dates: list[date] = []
    for y, mo, d in GREG_JP_RE.findall(scrubbed):
        try:
            dates.append(date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    if not dates:
        for mo, d in MD_RE.findall(scrubbed):
            month, day = int(mo), int(d)
            year = posted_year + (1 if posted_month >= 10 and month <= 3 else 0)
            try:
                dates.append(date(year, month, day))
            except ValueError:
                pass
    if not dates:
        return None
    return min(dates), max(dates)


def parse_detail(page_html: str, url: str, title_hint: str = "") -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    h1 = soup.find("h1")
    title = _clean_title(" ".join((h1.get_text(" ", strip=True) if h1 else title_hint).split()))
    if not title or not _is_target(title):
        return None
    text = " ".join(soup.get_text(" ", strip=True).split())
    date_range = _date_range(text)
    if not date_range:
        return None
    start, end = date_range
    venue = "明和町"
    for pattern in (r"会場[:：]\s*([^|｜]+)", r"開催場所[:：]\s*([^|｜]+)"):
        m = re.search(pattern, text)
        if m:
            venue = m.group(1).strip()
            break
    return {
        "title": title,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": venue,
        "prefecture": "三重県",
        "category": "祭り・季節",
        "source": "明和観光商社",
        "official_url": url,
        "decision": "display",
        "decision_reason": "明和観光商社公式で開催日を確認できた主要な祭・季節イベント",
    }


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "三重県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a, b = _norm(existing.get("title", "")), _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        listing = fetch_html(LIST_URL)
    except requests.RequestException as exc:
        print("MEIWA skipped: official event page unavailable", type(exc).__name__)
        return
    candidates = parse_listing(listing)
    found: list[dict] = []
    failed_details = 0
    for candidate in candidates:
        try:
            detail = fetch_html(candidate["url"], attempts=2)
        except requests.RequestException:
            failed_details += 1
            continue
        item = parse_detail(detail, candidate["url"], candidate["title"])
        if item and item["end_date"] >= today.isoformat():
            found.append(item)
    before = len(events)
    for item in sorted(found, key=lambda e: (e["start_date"], e["title"])):
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
    meta.update({"updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MEIWA candidates", len(candidates), "dated_future", len(found), "added", len(events) - before, "failed_details", failed_details)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
