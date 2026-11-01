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

URL = "https://www.ogakikanko.jp/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "大垣観光協会 水都旅"

MONTH_ONLY_RE = re.compile(r"^(\d{1,2})月$")
DATE_LINE_RE = re.compile(
    r"^(?:(\d{1,2})月)?\s*(\d{1,2})日(?:\s*[（(][^）)]*[）)])?"
    r"(?:\s*[〜～\-–—・]\s*(?:(\d{1,2})月)?\s*(\d{1,2})日(?:\s*[（(][^）)]*[）)])?)?\s*$"
)
NAV_WORDS = {
    "ホーム", "イベント", "イベント情報", "春", "夏", "秋", "冬", "詳細", "一覧", "観光情報",
    "大垣観光協会", "西美濃イベント情報", "日本語版", "外国語版",
}


def fetch_html(attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                URL,
                timeout=(10, 45),
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
            print(f"SEINO_SUITRIP retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def _year_for_month(base_year: int, current_month: int, month: int) -> int:
    if current_month >= 10 and month <= 3:
        return base_year + 1
    return base_year


def parse_date_line(text: str, current_month: int | None, base_year: int, now_month: int) -> tuple[str, str] | None:
    match = DATE_LINE_RE.match(_clean(text))
    if not match:
        return None
    start_month_raw, start_day_raw, end_month_raw, end_day_raw = match.groups()
    start_month = int(start_month_raw) if start_month_raw else current_month
    if start_month is None:
        return None
    start_day = int(start_day_raw)
    start_year = _year_for_month(base_year, now_month, start_month)
    try:
        start = date(start_year, start_month, start_day)
    except ValueError:
        return None

    if not end_day_raw:
        return start.isoformat(), start.isoformat()

    end_month = int(end_month_raw) if end_month_raw else start_month
    end_year = start_year
    if end_month < start_month and start_month >= 10 and end_month <= 3:
        end_year += 1
    try:
        end = date(end_year, end_month, int(end_day_raw))
    except ValueError:
        return None
    return start.isoformat(), end.isoformat()


def _is_title_candidate(text: str) -> bool:
    if not text or text in NAV_WORDS:
        return False
    if MONTH_ONLY_RE.match(text) or DATE_LINE_RE.match(text):
        return False
    if text.startswith("Copyright") or text.startswith("〒") or text.startswith("TEL") or text.startswith("FAX"):
        return False
    return len(text) >= 3


def category_for(title: str) -> str:
    lower = title.lower()
    if any(word in title for word in ("マルシェ", "マーケット", "グルメ", "食", "物産")):
        return "グルメ"
    if any(word in lower for word in ("マラソン", "run", "スポーツ", "大会")):
        return "スポーツ"
    if any(word in title for word in ("イルミ", "もみじ", "紅葉", "花火", "祭", "まつり")):
        return "祭り・季節"
    if any(word in title for word in ("コンサート", "音楽", "演奏", "ライブ")):
        return "コンサート・ショー"
    if any(word in title for word in ("美術展", "芸術祭", "作品展", "展示", "展覧")):
        return "展示会"
    return "イベント"


def parse_events(html: str, base_year: int, now_month: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    lines = [_clean(text) for text in soup.stripped_strings]
    lines = [line for line in lines if line]

    events: list[dict] = []
    current_month: int | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        month_match = MONTH_ONLY_RE.match(line)
        if month_match:
            current_month = int(month_match.group(1))
            i += 1
            continue

        dates = parse_date_line(line, current_month, base_year, now_month)
        if not dates:
            i += 1
            continue

        title = ""
        title_index = -1
        for j in range(i + 1, min(i + 5, len(lines))):
            candidate = lines[j]
            if _is_title_candidate(candidate):
                title = candidate
                title_index = j
                break
        if not title:
            i += 1
            continue

        venue = "西美濃"
        for j in range(title_index + 1, min(title_index + 4, len(lines))):
            candidate = lines[j]
            if MONTH_ONLY_RE.match(candidate) or DATE_LINE_RE.match(candidate):
                break
            if not _is_title_candidate(candidate):
                continue
            if len(candidate) <= 120:
                venue = candidate
                break

        events.append({
            "title": title,
            "start_date": dates[0],
            "end_date": dates[1],
            "venue": venue,
            "prefecture": "岐阜県",
            "category": category_for(title),
            "source": SOURCE,
            "official_url": URL,
            "decision": "display",
            "decision_reason": "大垣観光協会公式の西美濃イベント情報に掲載",
        })
        i = max(i + 1, title_index + 1)

    unique: dict[tuple[str, str], dict] = {}
    for event in events:
        unique[(_norm(event["title"]), event["start_date"])] = event
    return sorted(unique.values(), key=lambda event: (event["start_date"], event["title"]))


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県":
        return False
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    today = now.date().isoformat()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("SEINO_SUITRIP skipped: official event page unavailable", type(exc).__name__)
        return

    parsed = parse_events(html, now.year, now.month)
    future = [event for event in parsed if event["end_date"] >= today]

    before = len(events)
    for item in future:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)

    events.sort(key=lambda event: (event.get("start_date", ""), event.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {key: sum(event.get("decision") == key for event in events) for key in ("display", "hold", "exclude")}
    meta.update({
        "updated_at": now.isoformat(timespec="minutes"),
        "source_count": len({event.get("source") for event in events if event.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("SEINO_SUITRIP parsed", len(parsed), "future", len(future), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
