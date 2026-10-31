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

BASE = "https://www.visit-shizuoka.com"
LIST_URL = f"{BASE}/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DETAIL_RE = re.compile(r"/event/detail_\d+\.html$")
JP_DATE_RE = re.compile(r"(?:(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日")

TARGET_WORDS = (
    "祭", "まつり", "フェス", "フェスタ", "花火", "ライトアップ", "イルミ",
    "大道芸ワールドカップ", "ホビーのまち", "プラモデル選手権", "夜間特別拝観",
    "文化財特別公開",
)
MUSEUM_WORDS = (
    "静岡市美術館", "静岡市歴史博物館", "フェルケール博物館", "芹沢銈介美術館",
)
KNOWN_VENUES = (
    "ツインメッセ静岡", "静岡市美術館", "静岡市歴史博物館", "フェルケール博物館",
    "芹沢銈介美術館", "久能山東照宮", "駿府城公園",
)
EXCLUDE_WORDS = (
    "開催終了", "船宿記念館", "末廣", "着物体験", "置物作り", "ウォーキング",
    "スタンプ", "自転車旅", "ライド", "キャンペーン", "御城印", "講演", "教室",
    "パネル展", "ヌーン茶", "クルーズ", "関連イベント", "課外授業",
)


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
            print(f"SHIZUOKA_CITY retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _is_target(title: str) -> bool:
    if any(w.casefold() in title.casefold() for w in EXCLUDE_WORDS):
        return False
    if any(w.casefold() in title.casefold() for w in TARGET_WORDS):
        return True
    return any(w in title for w in MUSEUM_WORDS)


def discover_candidates(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(LIST_URL, a["href"])
        parsed = urlparse(url)
        if parsed.netloc not in ("visit-shizuoka.com", "www.visit-shizuoka.com"):
            continue
        if not DETAIL_RE.search(parsed.path) or url in seen:
            continue
        heading = a.find_previous("h3")
        if heading is None:
            continue
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title or not _is_target(title):
            continue
        seen.add(url)
        out.append((title, url))
    return out


def _labeled_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str | None:
    for dt in soup.find_all("dt"):
        key = " ".join(dt.get_text(" ", strip=True).split())
        if any(label in key for label in labels):
            dd = dt.find_next_sibling("dd")
            if dd:
                value = " ".join(dd.get_text(" ", strip=True).split())
                if value:
                    return value
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        key = " ".join(cells[0].get_text(" ", strip=True).split())
        if any(label in key for label in labels):
            value = " ".join(" ".join(c.get_text(" ", strip=True).split()) for c in cells[1:])
            if value:
                return value
    return None


def _inline_labeled_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str | None:
    text = unicodedata.normalize("NFKC", " ".join(soup.stripped_strings))
    stop = r"(?=\s*[〖【](?:開催|会場|場所|ライトアップ|観覧|問合|問い合|関連|アクセス|開館|休館|ウェブ|駐車|住所|電話)|$)"
    for label in labels:
        patterns = (
            rf"[〖【]\s*{re.escape(label)}\s*[〗】]\s*[：:]?\s*(.{{2,160}}?){stop}",
            rf"{re.escape(label)}\s*[：:]\s*(.{{2,160}}?){stop}",
        )
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                value = " ".join(m.group(1).split()).strip(" ・、。")
                if value:
                    return value
    return None


def parse_dates(text: str, today: date) -> tuple[date, date] | None:
    normalized = unicodedata.normalize("NFKC", text)
    matches = list(JP_DATE_RE.finditer(normalized))
    if not matches:
        return None
    values: list[date] = []
    current_year = today.year
    current_month: int | None = None
    for m in matches:
        year = int(m.group(1)) if m.group(1) else current_year
        month = int(m.group(2)) if m.group(2) else current_month
        if month is None:
            continue
        if not m.group(1) and current_month is not None and month < current_month:
            year = current_year + 1
        try:
            value = date(year, month, int(m.group(3)))
        except ValueError:
            continue
        values.append(value)
        current_year, current_month = value.year, value.month
    if not values:
        return None
    return values[0], values[-1]


def parse_detail(page_html: str, today: date) -> tuple[date, date, str] | None:
    soup = BeautifulSoup(page_html, "html.parser")
    date_text = _labeled_value(soup, ("開催期間", "開催日程", "開催日時", "開催日"))
    if not date_text:
        text = " ".join(soup.stripped_strings)
        m = re.search(r"(?:開催期間|開催日程|開催日時|開催日)[：:\s]*([^。]{4,180})", text)
        date_text = m.group(1) if m else text
    dates = parse_dates(date_text, today)
    if not dates:
        return None

    venue = _labeled_value(soup, ("開催場所", "会場")) or _inline_labeled_value(soup, ("開催場所", "会場"))
    if not venue:
        full_text = unicodedata.normalize("NFKC", " ".join(soup.stripped_strings))
        venue = next((name for name in KNOWN_VENUES if name in full_text), "静岡市")
    venue = " ".join(venue.split())[:120]
    return dates[0], dates[1], venue


def _fallback_venue(title: str, venue: str) -> str:
    for museum in MUSEUM_WORDS:
        if museum in title:
            return venue if museum in venue else museum
    if venue != "静岡市":
        return venue
    if "大道芸ワールドカップ" in title:
        return "駿府城公園ほか静岡市内各所"
    if "久能山東照宮" in title:
        return "久能山東照宮"
    if "文化財特別公開" in title:
        return "静岡市内各所"
    return venue


def category_for(title: str) -> str:
    if any(w in title for w in ("美術館", "博物館", "企画展", "企画展示")):
        return "展示会"
    if any(w in title for w in ("祭", "まつり", "フェス", "フェスタ", "花火", "ライトアップ", "イルミ", "夜間特別拝観")):
        return "祭り・季節"
    return "その他"


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
        listing = fetch_html(LIST_URL)
    except requests.RequestException as exc:
        print("SHIZUOKA_CITY skipped: official listing unavailable", type(exc).__name__)
        return

    candidates = discover_candidates(listing)
    found: list[dict] = []
    failed_details = 0
    for title, url in candidates[:30]:
        try:
            detail = fetch_html(url, attempts=2)
        except requests.RequestException:
            failed_details += 1
            continue
        parsed = parse_detail(detail, today)
        if not parsed:
            continue
        start, end, venue = parsed
        if end < today:
            continue
        venue = _fallback_venue(title, venue)
        found.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": venue,
            "prefecture": "静岡県",
            "category": category_for(title),
            "source": "静岡市観光ナビ",
            "official_url": url,
            "decision": "display",
            "decision_reason": "静岡市公式観光サイトから大規模な祭・季節催事・主要展覧会を抽出",
        })

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = list(unique.values())

    before = len(events)
    for item in sorted(found, key=lambda e: (e["start_date"], e["title"])):
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SHIZUOKA_CITY candidates", len(candidates), "future", len(found), "added", len(events) - before, "failed_details", failed_details)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
