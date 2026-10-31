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

from src.append_aichi_now import append_pickups

SOURCE_URL = "https://www.t-messe.or.jp/news_topics/index.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

HEADING_RE = re.compile(r"^(?P<m>\d{1,2})/(?P<d>\d{1,2})\s+(?P<title>.+)$")
DATE_RE = re.compile(r"(?:(?P<m>\d{1,2})月)?\s*(?P<d>\d{1,2})日")

TARGET_WORDS = (
    "モビリティ", "ハンドメイド", "コミック", "ミネラル", "タミヤ", "産業フェア", "フェス",
    "フェア", "マルシェ", "クラフト", "アニメ", "ゲーム", "ホビー", "自動車", "マツダ",
    "キャンピング", "アウトドア", "模型", "ミニ四駆", "天然石", "zine",
)
EXCLUDE_WORDS = (
    "商談会", "セミナー", "相談会", "関係者", "招待", "専門店", "就職", "展示大会",
)


def fetch_html(url: str = SOURCE_URL, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
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
        except requests.RequestException as exc:
            last_error = exc
            print(f"TWINMESSE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _nearest_year(month: int, day: int, today: date) -> int:
    candidates: list[tuple[int, int]] = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        candidates.append((abs((candidate - today).days), year))
    if not candidates:
        raise ValueError("invalid month/day")
    return min(candidates)[1]


def _dates_from_block(lines: list[str], today: date) -> tuple[date, date] | None:
    explicit_month: int | None = None
    values: list[tuple[int, int]] = []
    for line in lines[:6]:
        for m in DATE_RE.finditer(line):
            if m.group("m"):
                explicit_month = int(m.group("m"))
            if explicit_month is None:
                continue
            values.append((explicit_month, int(m.group("d"))))
        if values:
            # The first line with dates is the event period. Later lines are usually daily hours.
            break
    if not values:
        return None

    sm, sd = values[0]
    try:
        sy = _nearest_year(sm, sd, today)
        start = date(sy, sm, sd)
    except ValueError:
        return None

    em, ed = values[-1]
    ey = sy + (1 if em < sm else 0)
    try:
        end = date(ey, em, ed)
    except ValueError:
        return None
    return start, end


def _venue_from_block(lines: list[str]) -> str:
    for line in lines:
        m = re.search(r"〖会場〗\s*(.+)$", line)
        if m:
            venue = m.group(1).strip()
            return f"ツインメッセ静岡 {venue}" if venue else "ツインメッセ静岡"
    return "ツインメッセ静岡"


def _description_from_block(lines: list[str]) -> str:
    parts: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith("〖催事内容〗"):
            parts.append(line.replace("〖催事内容〗", "", 1).strip())
            collecting = True
            continue
        if collecting:
            if line.startswith("〖"):
                break
            parts.append(line)
    return " ".join(p for p in parts if p)


def _is_target(title: str, description: str) -> bool:
    text = f"{title} {description}"
    if any(word.casefold() in text.casefold() for word in EXCLUDE_WORDS):
        return False
    return any(word.casefold() in text.casefold() for word in TARGET_WORDS)


def _category(title: str, description: str) -> str:
    text = f"{title} {description}".casefold()
    if any(word in text for word in ("コミック", "アニメ", "ゲーム", "タミヤ", "ミニ四駆", "模型")):
        return "ゲーム"
    if any(word in text for word in ("モビリティ", "自動車", "マツダ", "キャンピング")):
        return "展示会"
    if any(word in text for word in ("フェス", "フェア", "マルシェ", "ハンドメイド", "クラフト")):
        return "祭り・季節"
    return "展示会"


def parse_events(page_html: str, today: date) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [_clean(s) for s in soup.stripped_strings if _clean(s)]
    heading_indexes: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            heading_indexes.append((i, _clean(m.group("title"))))

    events: list[dict] = []
    for pos, (index, title) in enumerate(heading_indexes):
        end_index = heading_indexes[pos + 1][0] if pos + 1 < len(heading_indexes) else min(index + 25, len(lines))
        block = lines[index + 1:end_index]
        dates = _dates_from_block(block, today)
        if not dates:
            continue
        start, end = dates
        description = _description_from_block(block)
        if not _is_target(title, description):
            continue
        events.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": _venue_from_block(block),
            "prefecture": "静岡県",
            "category": _category(title, description),
            "source": "ツインメッセ静岡",
            "official_url": SOURCE_URL,
            "decision": "display",
            "decision_reason": "ツインメッセ静岡公式掲載の一般向け大型・対象ジャンルイベント",
        })

    unique: dict[tuple[str, str], dict] = {}
    for event in events:
        unique[(event["title"], event["start_date"])] = event
    return sorted(unique.values(), key=lambda e: (e["start_date"], e["title"]))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        parsed = parse_events(fetch_html(), today)
    except requests.RequestException as exc:
        print("TWINMESSE skipped: official source unavailable", type(exc).__name__)
        return

    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("ツインメッセ静岡公式から今後の対象イベントを取得できませんでした。")

    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {k: sum(e.get("decision") == k for e in merged) for k in ("display", "hold", "exclude")}
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("TWINMESSE parsed", len(parsed), "future", len(found), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
