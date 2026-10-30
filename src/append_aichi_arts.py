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

BASE = "https://www-stage.aac.pref.aichi.jp"
EVENTS_URL = BASE + "/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

FULL_DATE_RE = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日")
FOLLOW_DAY_RE = re.compile(r"[・〜～\-]\s*(\d{1,2})日")


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
            print(f"AICHI_ARTS retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def parse_dates(text: str) -> tuple[str, str] | None:
    m = FULL_DATE_RE.search(text)
    if not m:
        return None
    year, month, day = map(int, m.groups())
    start = date(year, month, day)
    end = start
    tail = text[m.end():]
    dm = FOLLOW_DAY_RE.search(tail)
    if dm:
        try:
            end = date(year, month, int(dm.group(1)))
        except ValueError:
            end = start
    return start.isoformat(), end.isoformat()


def _text_with_nearby_date(anchor) -> str:
    node = anchor
    for _ in range(12):
        node = node.parent
        if node is None:
            break
        text = " ".join(node.get_text(" ", strip=True).split())
        if FULL_DATE_RE.search(text) and len(text) <= 3000:
            return text

    previous = anchor.find_previous(string=FULL_DATE_RE)
    if previous:
        return str(previous)
    following = anchor.find_next(string=FULL_DATE_RE)
    if following:
        return str(following)
    return ""


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("演劇", "ゴドー", "ダンス", "バレエ", "performing arts")):
        return "コンサート・ショー"
    if any(w in t for w in ("管弦楽", "オルガン", "コンサート", "演奏", "音楽")):
        return "コンサート・ショー"
    return "その他"


def parse_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[str] = set()

    # 本番サイトは相対リンク/絶対リンクのどちらもあり得るため detail/ で拾う。
    for anchor in soup.select('a[href*="detail/"]'):
        href = anchor.get("href", "").strip()
        if not href:
            continue
        url = urljoin(EVENTS_URL, href)
        if "/event/detail/" not in url or url in seen:
            continue

        title = " ".join(anchor.get_text(" ", strip=True).split()).strip()
        if not title:
            continue
        if any(word in title for word in ("募集", "応募締切", "審査結果")):
            continue

        text = _text_with_nearby_date(anchor)
        dates = parse_dates(text)
        if not dates:
            continue

        start_date, end_date = dates
        out.append({
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "venue": "愛知県芸術劇場",
            "category": category_for(title),
            "official_url": url,
        })
        seen.add(url)

    return out


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    if "愛知県芸術劇場" not in existing.get("venue", ""):
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
        html = fetch_html(EVENTS_URL)
    except requests.RequestException as exc:
        print("AICHI_ARTS skipped: source unavailable", type(exc).__name__)
        return

    found = [e for e in parse_events(html) if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("愛知県芸術劇場の自主事業を取得できませんでした。サイト構造変更の可能性があります。")

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
            "category": item["category"],
            "source": "愛知県芸術劇場",
            "official_url": item["official_url"],
            "decision": "display",
            "decision_reason": "愛知県芸術劇場公式の自主事業一覧掲載公演",
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

    print("AICHI_ARTS found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
