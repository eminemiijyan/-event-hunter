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

URL = "https://www.city.ogaki.lg.jp/0000006990.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "大垣市 こどもまんなか水都っ子月間"

DATE_TOKEN_RE = re.compile(r"(?:(?:令和\s*(\d+)年)|(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日")
SKIP_TITLES = ("水都っ子月間とは", "秋のこどもまんなか水都っ子月間", "イベント紹介")


def fetch_html(attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(URL, timeout=(10, 40), headers={
                "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                "Accept-Language": "ja-JP,ja;q=0.9",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"OGAKI_FAMILY retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def parse_dates(text: str, base_year: int) -> tuple[str, str] | None:
    values: list[date] = []
    current_year = base_year
    current_month: int | None = None
    for match in DATE_TOKEN_RE.finditer(_clean(text)):
        era_year, western_year, month, day = match.groups()
        if era_year:
            current_year = 2018 + int(era_year)
        elif western_year:
            current_year = int(western_year)
        if month:
            current_month = int(month)
        if current_month is None:
            continue
        try:
            values.append(date(current_year, current_month, int(day)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def _section_text(heading) -> str:
    parts: list[str] = []
    for sibling in heading.next_siblings:
        name = getattr(sibling, "name", None)
        if name in ("h2", "h3", "h4"):
            break
        if hasattr(sibling, "get_text"):
            text = _clean(sibling.get_text(" ", strip=True))
        else:
            text = _clean(str(sibling))
        if text:
            parts.append(text)
    return " ".join(parts)


def _venue_from_text(text: str) -> str:
    match = re.search(r"(?:ところ|場所|会場)\s*[:：]?\s*(.+?)(?=\s+(?:内容|対象|定員|問い合わせ|協力|参加|申込)\b|$)", text)
    if match:
        return _clean(match.group(1))[:180]
    return "大垣市内"


def category_for(title: str) -> str:
    if any(word in title for word in ("コンサート", "吹奏楽", "音楽")):
        return "コンサート・ショー"
    if any(word in title for word in ("ボッチャ", "スポーツ", "選手権")):
        return "スポーツ"
    if any(word in title for word in ("ギャラリー", "展示", "作品展")):
        return "展示会"
    return "イベント"


def parse_events(html: str, base_year: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    for heading in soup.find_all(["h3", "h4"]):
        title = _clean(heading.get_text(" ", strip=True))
        if not title or any(skip in title for skip in SKIP_TITLES):
            continue
        details = _section_text(heading)
        dates = parse_dates(details, base_year)
        if not dates:
            continue
        events.append({
            "title": title,
            "start_date": dates[0],
            "end_date": dates[1],
            "venue": _venue_from_text(details),
            "prefecture": "岐阜県",
            "category": category_for(title),
            "source": SOURCE,
            "official_url": URL,
            "decision": "display",
            "decision_reason": "大垣市公式のこども・親子向けイベント紹介に掲載",
        })
    unique: dict[tuple[str, str], dict] = {}
    for event in events:
        unique[(_norm(event["title"]), event["start_date"])] = event
    return sorted(unique.values(), key=lambda event: (event["start_date"], event["title"]))


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a, b = _norm(existing.get("title", "")), _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    events_path, meta_path = SITE_DIR / "events.json", SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("OGAKI_FAMILY skipped: official page unavailable", type(exc).__name__)
        return

    parsed = parse_events(html, now.year)
    future = [event for event in parsed if event["end_date"] >= now.date().isoformat()]
    before = len(events)
    for item in future:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda event: (event.get("start_date", ""), event.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {key: sum(event.get("decision") == key for event in events) for key in ("display", "hold", "exclude")}
    meta.update({"updated_at": now.isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OGAKI_FAMILY parsed", len(parsed), "future", len(future), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
