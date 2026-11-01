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

URL = "https://minokamo-kanko.jp/contents/%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E6%83%85%E5%A0%B1/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "みのかもとりっぷ"

MAJOR_WORDS = (
    "遊園地", "イルミネーション", "フェス", "FES", "万博", "マルシェ", "マーケット",
    "多文化交流", "トレイル", "祭", "まつり", "花火", "キャンプ場", "縁日",
)
SMALL_WORDS = ("体験", "教室", "ヨガ", "病院", "撮影会", "スワッグ", "収穫", "ミニゲーム")
DATE_TOKEN_RE = re.compile(r"(?:(20\d{2})年\s*)?(?:(\d{1,2})月\s*)?(\d{1,2})日")


def fetch_html(attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(URL, timeout=(10, 45), headers={
                "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                "Accept-Language": "ja-JP,ja;q=0.9",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"MINOKAMO_KANKO retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def parse_period(text: str, base_year: int) -> tuple[str, str] | None:
    text = _clean(text)
    values: list[date] = []
    year = base_year
    month: int | None = None
    prev_month: int | None = None
    for match in DATE_TOKEN_RE.finditer(text):
        year_token, month_token, day_token = match.groups()
        if year_token:
            year = int(year_token)
        if month_token:
            new_month = int(month_token)
            if not year_token and prev_month is not None and new_month < prev_month and prev_month >= 10 and new_month <= 3:
                year += 1
            month = new_month
            prev_month = new_month
        if month is None:
            continue
        try:
            values.append(date(year, month, int(day_token)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def _section_text(heading) -> str:
    parts: list[str] = []
    for sibling in heading.next_siblings:
        name = getattr(sibling, "name", None)
        if name in ("h2", "h3", "h4", "h5"):
            break
        if hasattr(sibling, "get_text"):
            text = _clean(sibling.get_text(" ", strip=True))
        else:
            text = _clean(str(sibling))
        if text:
            parts.append(text)
    return " ".join(parts)


def category_for(title: str) -> str:
    if any(word in title for word in ("万博", "マルシェ", "マーケット", "キッチンカー")):
        return "グルメ"
    if any(word in title for word in ("イルミ", "祭", "まつり", "花火")):
        return "祭り・季節"
    if any(word.lower() in title.lower() for word in ("trail", "トレイル", "スポーツ", "大会")):
        return "スポーツ"
    if any(word.lower() in title.lower() for word in ("fes", "フェス")):
        return "イベント"
    return "イベント"


def parse_events(html: str, base_year: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []
    for heading in soup.find_all(["h4", "h5"]):
        title = _clean(heading.get_text(" ", strip=True))
        if not title or any(word in title for word in SMALL_WORDS):
            continue
        if not any(word.lower() in title.lower() for word in MAJOR_WORDS):
            continue
        details = _section_text(heading)
        period = parse_period(details, base_year)
        if not period:
            continue
        venue_match = re.search(r"(?:場所|会場)[:：]\s*([^＊*]+?)(?=\s+(?:参加|料金|詳細|応募|定員|時間|日時|期間)[:：]|$)", details)
        venue = _clean(venue_match.group(1)) if venue_match else "美濃加茂市内"
        out.append({
            "title": title,
            "start_date": period[0], "end_date": period[1],
            "venue": venue,
            "prefecture": "岐阜県",
            "category": category_for(title),
            "source": SOURCE,
            "official_url": URL,
            "decision": "display",
            "decision_reason": "美濃加茂市観光協会公式イベント情報に掲載",
        })
    return out


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
        print("MINOKAMO_KANKO skipped: official page unavailable", type(exc).__name__)
        return
    parsed = parse_events(html, now.year)
    future = [e for e in parsed if e["end_date"] >= now.date().isoformat()]
    before = len(events)
    for item in future:
        if not any(_same_event(e, item) for e in events):
            events.append(item)
    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
    meta.update({"updated_at": now.isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MINOKAMO_KANKO parsed", len(parsed), "future", len(future), "added", len(events)-before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
