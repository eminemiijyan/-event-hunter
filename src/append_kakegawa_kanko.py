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

LIST_URL = "https://www.kakegawa-kankou.com/news/10782/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_PREFIX_RE = re.compile(
    r"^[・･]?\s*(\d{1,2})/(\d{1,2})"
    r"(?:\s*[～〜~\-]\s*(?:(\d{1,2})/)?(\d{1,2}))?\s+(.+)$"
)
TARGET_WORDS = (
    "祭", "まつり", "フェス", "FES", "フェスタ", "グルメサミット", "百鬼夜行",
    "イルミ", "ライトアップ", "アートデイズ", "文化展",
)
EXCLUDE_WORDS = (
    "茶会", "一般公開", "ウォーク", "原画展", "コンテスト", "募集", "教室", "講座",
    "駅伝", "スポーツチャレンジ", "消防フェア", "マルシャン", "販売",
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
            print(f"KAKEGAWA_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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
    return any(w.casefold() in title.casefold() for w in TARGET_WORDS)


def _event_year(month: int, today: date) -> int:
    return today.year + (1 if today.month >= 10 and month <= 3 else 0)


def _venue_from_title(title: str) -> tuple[str, str]:
    m = re.search(r"[＠@]\s*([^（(]+)$", title)
    if m:
        venue = m.group(1).strip()
        clean = title[:m.start()].strip()
        return clean, venue
    m = re.search(r"[（(]([^）)]+)[）)]\s*$", title)
    if m:
        venue = m.group(1).strip()
        clean = title[:m.start()].strip()
        return clean, venue
    return title.strip(), "掛川市"


def category_for(title: str) -> str:
    if any(w in title for w in ("グルメ", "商工まつり")):
        return "グルメ"
    if any(w in title for w in ("アート", "文化展")):
        return "展示会"
    return "祭り・季節"


def parse_events(page_html: str, today: date) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [unicodedata.normalize("NFKC", " ".join(line.split())) for line in soup.get_text("\n", strip=True).splitlines()]
    in_events = False
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for line in lines:
        if "イベント情報" in line:
            in_events = True
            continue
        if in_events and "観光施設の営業情報" in line:
            break
        if not in_events:
            continue
        m = DATE_PREFIX_RE.match(line)
        if not m:
            continue
        sm, sd = int(m.group(1)), int(m.group(2))
        em = int(m.group(3) or sm)
        ed = int(m.group(4) or sd)
        title_raw = m.group(5).strip()
        if not _is_target(title_raw):
            continue
        sy = _event_year(sm, today)
        ey = sy + (1 if em < sm else 0)
        try:
            start = date(sy, sm, sd)
            end = date(ey, em, ed)
        except ValueError:
            continue
        if end < today:
            continue
        title, venue = _venue_from_title(title_raw)
        key = (_norm(title), start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": venue,
            "prefecture": "静岡県",
            "category": category_for(title),
            "source": "掛川観光協会",
            "official_url": LIST_URL,
            "decision": "display",
            "decision_reason": "掛川観光協会公式の最新イベント情報から祭・フェス・大型季節イベントを抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


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
        print("KAKEGAWA_KANKO skipped: official current-info page unavailable", type(exc).__name__)
        return

    found = parse_events(html, today)
    before = len(events)
    for item in found:
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
    print("KAKEGAWA_KANKO found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
