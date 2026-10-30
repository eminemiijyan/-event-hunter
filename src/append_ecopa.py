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

BASE = "https://www.ecopa.jp"
LIST_URL = f"{BASE}/event_list/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
ROW_RE = re.compile(r"^(20\d{2})\.(\d{1,2})\.(\d{1,2})\s+(.+)$")
FACILITIES = ("エコパスタジアム", "エコパアリーナ", "公園", "その他")
CATEGORIES = ("コンサート", "スタジアムコンサート", "アイスショー", "スポーツ", "サッカー", "ラグビーリーグワン", "イベント", "エコパ自主事業")
EXCLUDE_WORDS = ("自然塾", "見学ツアー", "個人利用", "養生", "準備", "注意", "開花情報", "FDG in エコパ")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 45), headers={
                "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                "Accept-Language": "ja-JP,ja;q=0.9",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"ECOPA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _split_body(body: str) -> tuple[str, str, str]:
    venue = "エコパ"
    rest = body.strip()
    for facility in FACILITIES:
        if rest.startswith(facility):
            venue = facility
            rest = rest[len(facility):].strip()
            break
    category = "イベント"
    matched = True
    while matched:
        matched = False
        for cat in CATEGORIES:
            if rest.startswith(cat):
                category = cat
                rest = rest[len(cat):].strip()
                matched = True
                break
    return venue, category, rest


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    grouped: dict[tuple[str, str], dict] = {}
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        m = ROW_RE.match(text)
        if not m:
            continue
        y, mo, d = map(int, m.group(1, 2, 3))
        try:
            event_date = date(y, mo, d)
        except ValueError:
            continue
        venue, category, title = _split_body(m.group(4))
        if not title or any(w in title for w in EXCLUDE_WORDS):
            continue
        url = urljoin(BASE, a["href"])
        key = (_norm(title), url)
        if key not in grouped:
            grouped[key] = {
                "title": title,
                "start_date": event_date.isoformat(),
                "end_date": event_date.isoformat(),
                "venue": venue if venue.startswith("エコパ") else f"エコパ {venue}",
                "prefecture": "静岡県",
                "category": "コンサート・舞台" if "コンサート" in category else ("スポーツ" if any(w in category for w in ("スポーツ", "サッカー", "ラグビー")) else "イベント"),
                "source": "エコパ",
                "official_url": url,
                "decision": "display",
                "decision_reason": "エコパ公式イベント情報に掲載された主要な公開イベントを抽出",
            }
        else:
            grouped[key]["start_date"] = min(grouped[key]["start_date"], event_date.isoformat())
            grouped[key]["end_date"] = max(grouped[key]["end_date"], event_date.isoformat())
    return sorted(grouped.values(), key=lambda e: (e["start_date"], e["title"]))


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "静岡県" or existing.get("start_date") != candidate.get("start_date"):
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
        html = fetch_html(LIST_URL)
    except requests.RequestException as exc:
        print("ECOPA skipped: official event list unavailable", type(exc).__name__)
        return
    found = [e for e in parse_listing(html) if e["end_date"] >= today.isoformat()]
    before = len(events)
    for item in found:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
    meta.update({"updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ECOPA parsed", len(parse_listing(html)), "future", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
