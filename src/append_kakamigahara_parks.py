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

URL = "https://www.city.kakamigahara.lg.jp/event/1005356/1017251/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "各務原市 公園イベント情報"

REIWA_DATE_RE = re.compile(r"令和\s*(\d+)年\s*(\d{1,2})月\s*(\d{1,2})日")
VENUE_HEADINGS = ("市民公園", "学びの森", "河跡湖公園", "各務野自然遺産の森")
EXCLUDE_WORDS = ("使用予定", "工事", "点検", "清掃", "休園")


def fetch_html(url: str = URL, attempts: int = 3) -> str:
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
            print(f"KAKAMIGAHARA_PARKS retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def parse_reiwa_date(text: str) -> str | None:
    match = REIWA_DATE_RE.search(unicodedata.normalize("NFKC", text))
    if not match:
        return None
    era_year, month, day = map(int, match.groups())
    try:
        return date(2018 + era_year, month, day).isoformat()
    except ValueError:
        return None


def _following_text(heading) -> str:
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


def category_for(title: str, details: str) -> str:
    text = f"{title} {details}"
    if any(word in text for word in ("マーケット", "マルシェ", "キッチンカー", "物販", "フェア")):
        return "グルメ"
    if any(word in text for word in ("音楽", "ライブ", "演奏", "ダンス", "ステージ")):
        return "コンサート・ショー"
    if any(word in text for word in ("祭", "ハロウィン", "イルミ", "クリスマス")):
        return "祭り・季節"
    if any(word in text for word in ("スポーツ", "大会", "ラン", "サイクル")):
        return "スポーツ"
    return "イベント"


def parse_events(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    current_venue = "各務原市内公園"
    current_date: str | None = None
    events: list[dict] = []

    for heading in soup.find_all(["h2", "h3", "h4"]):
        text = _clean(heading.get_text(" ", strip=True))
        if not text:
            continue

        if heading.name == "h2":
            for venue in VENUE_HEADINGS:
                if venue in text:
                    current_venue = venue
                    break
            continue

        if heading.name == "h3":
            parsed = parse_reiwa_date(text)
            if parsed:
                current_date = parsed
            continue

        if heading.name != "h4" or current_date is None:
            continue
        if any(word in text for word in EXCLUDE_WORDS):
            continue

        details = _following_text(heading)
        events.append({
            "title": text,
            "start_date": current_date,
            "end_date": current_date,
            "venue": current_venue,
            "prefecture": "岐阜県",
            "category": category_for(text, details),
            "source": SOURCE,
            "official_url": URL,
            "decision": "display",
            "decision_reason": "各務原市公式の公園イベント情報に掲載",
        })
    return events


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県":
        return False
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("KAKAMIGAHARA_PARKS skipped: official page unavailable", type(exc).__name__)
        return

    parsed = parse_events(html)
    future = [event for event in parsed if event["end_date"] >= today]

    before = len(events)
    for item in future:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)

    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {key: sum(e.get("decision") == key for e in events) for key in ("display", "hold", "exclude")}
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("KAKAMIGAHARA_PARKS parsed", len(parsed), "future", len(future), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
