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

URL = "https://www.town.ibigawa.lg.jp/site/kankou/2431.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "揖斐川町 観光イベントカレンダー"

HEADING_RE = re.compile(r"令和\s*(\d+)年\s*(\d{1,2})月.*イベント情報")
DATE_RE = re.compile(r"(?:(\d{1,2})月)?\s*(\d{1,2})日")


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
            print(f"IBIGAWA_KANKO retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def parse_dates(text: str, year: int, default_month: int) -> tuple[str, str] | None:
    values: list[date] = []
    current_month = default_month
    for month_raw, day_raw in DATE_RE.findall(_clean(text)):
        if month_raw:
            current_month = int(month_raw)
        try:
            values.append(date(year, current_month, int(day_raw)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def category_for(title: str) -> str:
    if any(word in title for word in ("マルシェ", "フェスティバル", "物産", "産業")):
        return "イベント"
    if any(word in title for word in ("マラソン", "スポーツ", "大会", "クラシックカー")):
        return "スポーツ"
    if any(word in title for word in ("もみじ", "祭", "まつり", "花火")):
        return "祭り・季節"
    if any(word in title for word in ("企画展", "特別展", "展示")):
        return "展示会"
    return "イベント"


def parse_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    current_year: int | None = None
    current_month: int | None = None

    for node in soup.find_all(["h2", "h3", "h4", "table"]):
        if node.name != "table":
            text = _clean(node.get_text(" ", strip=True))
            match = HEADING_RE.search(text)
            if match:
                current_year = 2018 + int(match.group(1))
                current_month = int(match.group(2))
            continue

        if current_year is None or current_month is None:
            continue
        for tr in node.find_all("tr"):
            cells = [_clean(cell.get_text(" ", strip=True)) for cell in tr.find_all(["td", "th"])]
            if len(cells) < 3 or cells[0] in ("日にち", "日程"):
                continue
            dates = parse_dates(cells[0], current_year, current_month)
            if not dates:
                continue
            title = cells[1]
            venue = cells[2] or "揖斐川町内"
            if not title:
                continue
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
                "decision_reason": "揖斐川町公式観光イベントカレンダーに掲載",
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
        print("IBIGAWA_KANKO skipped: official page unavailable", type(exc).__name__)
        return

    parsed = parse_events(html)
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
    print("IBIGAWA_KANKO parsed", len(parsed), "future", len(future), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
