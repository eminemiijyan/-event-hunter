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

BASE = "https://www.oasispark.co.jp"
LIST_URLS = [
    BASE + "/event/%E9%96%8B%E5%82%AC%E6%9C%9F%E9%96%93/",
    BASE + "/event/page/2/",
    BASE + "/event/page/3/",
]
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "オアシスパーク"
DEFAULT_VENUE = "河川環境楽園 オアシスパーク"

DETAIL_RE = re.compile(r"/event/20\d{2}/\d{1,2}/\d+/?$")
DATE_TOKEN_RE = re.compile(
    r"(?P<full>20\d{2}[.年]\d{1,2}[/月]\d{1,2})"
    r"|(?P<md>(?<![\d.])\d{1,2}/\d{1,2})"
    r"|(?P<day>(?<![/\d])\d{1,2}(?=\s*[日(（]))"
)

EXCLUDE_WORDS = (
    "bbqママ会", "プラン", "お知らせ", "休園", "営業時間", "駐車場",
)


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                timeout=(10, 40),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                    "Accept-Language": "ja-JP,ja;q=0.9",
                },
            )
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"OASISPARK retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def parse_period(text: str) -> tuple[str, str] | None:
    normalized = unicodedata.normalize("NFKC", text).replace("月", "/").replace("年", ".")
    dates: list[date] = []
    year: int | None = None
    month: int | None = None

    for match in DATE_TOKEN_RE.finditer(normalized):
        token = match.group(0)
        try:
            if match.group("full"):
                full = re.match(r"(20\d{2})[.](\d{1,2})/(\d{1,2})", token)
                if not full:
                    continue
                year, month, day = map(int, full.groups())
            elif match.group("md"):
                if year is None:
                    continue
                new_month, day = map(int, token.split("/"))
                if month is not None and new_month < month and month >= 10 and new_month <= 3:
                    year += 1
                month = new_month
            else:
                if year is None or month is None:
                    continue
                day = int(token)
            dates.append(date(year, month, day))
        except ValueError:
            continue

    if not dates:
        return None
    return min(dates).isoformat(), max(dates).isoformat()


def _card_text(anchor) -> str:
    node = anchor
    best = " ".join(anchor.get_text(" ", strip=True).split())
    for _ in range(7):
        node = node.parent
        if node is None:
            break
        text = " ".join(node.get_text(" ", strip=True).split())
        if re.search(r"20\d{2}[.年]\d{1,2}[/月]\d{1,2}", text):
            best = text
            if len(text) < 1600:
                return text
    return best


def extract_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[dict] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        url = urljoin(BASE, anchor["href"])
        if urlparse(url).netloc != urlparse(BASE).netloc:
            continue
        if not DETAIL_RE.search(urlparse(url).path):
            continue
        if url in seen:
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        if not title or len(title) < 2:
            continue
        text = _card_text(anchor)
        period = parse_period(text)
        if not period:
            continue
        cards.append({"title": title, "url": url, "start_date": period[0], "end_date": period[1]})
        seen.add(url)
    return cards


def _is_candidate(title: str) -> bool:
    lower = unicodedata.normalize("NFKC", title).casefold()
    return not any(word in lower for word in EXCLUDE_WORDS)


def category_for(title: str) -> str:
    text = unicodedata.normalize("NFKC", title)
    if any(word in text for word in ("マルシェ", "マーケット", "グルメ", "フード", "パン")):
        return "グルメ"
    if any(word in text for word in ("祭", "ハロウィン", "キャンドル", "クリスマス", "イルミ", "花火")):
        return "祭り・季節"
    if any(word in text.lower() for word in ("cycle", "サイクル", "スポーツ", "大会")):
        return "スポーツ"
    if any(word in text for word in ("演奏", "ライブ", "コンサート", "ダンス", "ステージ")):
        return "コンサート・ショー"
    if any(word in text for word in ("体験", "釣堀", "釣り", "動物", "スタンプラリー", "水遊び", "昆虫")):
        return "イベント"
    return "イベント"


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県":
        return False
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    cards: list[dict] = []
    failed_pages = 0
    for url in LIST_URLS:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException as exc:
            failed_pages += 1
            print("OASISPARK list skipped", type(exc).__name__, url)
            continue
        found = extract_cards(html)
        print("OASISPARK page", url, "cards", len(found))
        cards.extend(found)

    unique: dict[str, dict] = {}
    for card in cards:
        unique[card["url"]] = card

    candidates: list[dict] = []
    for card in unique.values():
        if card["end_date"] < today.isoformat() or not _is_candidate(card["title"]):
            continue
        candidates.append({
            "title": card["title"],
            "start_date": card["start_date"],
            "end_date": card["end_date"],
            "venue": DEFAULT_VENUE,
            "prefecture": "岐阜県",
            "category": category_for(card["title"]),
            "source": SOURCE,
            "official_url": card["url"],
            "decision": "display",
            "decision_reason": "オアシスパーク公式イベント掲載",
        })

    candidates.sort(key=lambda item: (item["start_date"], item["title"]))
    before = len(events)
    for item in candidates:
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

    print(
        "OASISPARK unique", len(unique), "future", len(candidates),
        "added", len(events) - before, "failed_pages", failed_pages,
    )
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
