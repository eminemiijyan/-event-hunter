from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

URL = "https://www.suzukacircuit.jp/calendar_s/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

CATEGORY_LABELS = {"パークイベント", "4輪レース", "2輪レース", "コースイベント"}
MAJOR_MOTORSPORT_WORDS = (
    "FIA F1",
    "F1世界選手権",
    "日本グランプリ",
    "FIM世界耐久選手権",
    "鈴鹿8時間耐久",
    "SUPER GT",
    "スーパーフォーミュラ",
    "全日本ロードレース",
    "MFJグランプリ",
    "スーパー耐久",
    "Intercontinental GT Challenge",
    "SUZUKA 1000km",
)

DATE_START_RE = re.compile(r"(?:(20\d{2})年)?\s*(\d{1,2})月\s*(\d{1,2})日")
SPAN_RE = re.compile(
    r"(?:(?P<sy>20\d{2})年)?\s*(?P<sm>\d{1,2})月\s*(?P<sd>\d{1,2})日"
    r"(?:（[^）]*）|\([^)]*\))?"
    r"\s*(?P<sep>[～〜~\-–—・])\s*"
    r"(?:(?P<ey>20\d{2})年)?\s*(?:(?P<em>\d{1,2})月\s*)?(?P<ed>\d{1,2})日"
)
SINGLE_RE = re.compile(r"(?:(?P<y>20\d{2})年)?\s*(?P<m>\d{1,2})月\s*(?P<d>\d{1,2})日")
MONTH_HEADING_RE = re.compile(r"^\d{1,2}月[A-Za-z]+$")


def fetch_html(url: str = URL, attempts: int = 3) -> str:
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
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"SUZUKA retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def parse_date_span(text: str, default_year: int) -> tuple[date, date] | None:
    text = " ".join(text.split())
    m = SPAN_RE.search(text)
    if m:
        sy = int(m.group("sy") or default_year)
        sm = int(m.group("sm"))
        sd = int(m.group("sd"))
        em = int(m.group("em") or sm)
        ed = int(m.group("ed"))
        ey = int(m.group("ey")) if m.group("ey") else sy + (1 if em < sm else 0)
        try:
            return date(sy, sm, sd), date(ey, em, ed)
        except ValueError:
            return None

    m = SINGLE_RE.search(text)
    if not m:
        return None
    try:
        value = date(
            int(m.group("y") or default_year),
            int(m.group("m")),
            int(m.group("d")),
        )
    except ValueError:
        return None
    return value, value


def _is_date_line(text: str) -> bool:
    return bool(DATE_START_RE.search(text))


def _clean_title(text: str) -> str:
    text = " ".join(text.split())
    text = re.sub(r"\s*（外部サイト）\s*", " ", text)
    text = re.sub(r"\s*[｜|]\s*(?:フルコース|南コース|東コース).*$", "", text)
    return " ".join(text.split()).strip()


def _is_major(category: str, title: str) -> bool:
    if category == "パークイベント":
        return True
    folded = title.casefold()
    return any(word.casefold() in folded for word in MAJOR_MOTORSPORT_WORDS)


def parse_calendar(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    visible = " ".join(soup.stripped_strings)
    year_match = re.search(r"\[(20\d{2})年\]\s*レース", visible)
    if not year_match:
        raise ValueError("鈴鹿サーキット年間カレンダーの対象年を確認できませんでした。")
    base_year = int(year_match.group(1))

    lines = [" ".join(s.split()) for s in soup.stripped_strings]
    parsed: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _is_date_line(line):
            i += 1
            continue

        date_text = line
        next_i = i + 1
        if line.rstrip().endswith(("～", "〜", "~", "-", "–", "—", "・")) and next_i < len(lines):
            date_text += " " + lines[next_i]
            next_i += 1

        dates = parse_date_span(date_text, base_year)
        if not dates:
            i += 1
            continue

        block_end = next_i
        while block_end < len(lines):
            if _is_date_line(lines[block_end]) or MONTH_HEADING_RE.match(lines[block_end]):
                break
            block_end += 1

        j = next_i
        while j < block_end:
            if lines[j] not in CATEGORY_LABELS:
                j += 1
                continue

            category = lines[j]
            k = j + 1
            parts: list[str] = []
            while k < block_end and lines[k] not in CATEGORY_LABELS:
                if lines[k].startswith("※") or "施設点検のため休業" in lines[k]:
                    break
                parts.append(lines[k])
                k += 1

            title = _clean_title(" ".join(parts))
            if title and _is_major(category, title):
                start_date, end_date = dates
                parsed.append({
                    "title": title,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "venue": "鈴鹿サーキット",
                    "prefecture": "三重県",
                    "category": "祭り・季節" if category == "パークイベント" else "スポーツ",
                    "source": "鈴鹿サーキット",
                    "official_url": URL,
                    "decision": "display",
                    "decision_reason": (
                        "鈴鹿サーキット公式のパーク大型企画"
                        if category == "パークイベント"
                        else "鈴鹿サーキット公式の主要モータースポーツ"
                    ),
                })
            j = max(k, j + 1)

        i = max(block_end, i + 1)

    unique: dict[tuple[str, str, str], dict] = {}
    for event in parsed:
        key = (event["title"], event["start_date"], event["end_date"])
        unique[key] = event
    return list(unique.values())


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("SUZUKA skipped: source unavailable", type(exc).__name__)
        return

    parsed = parse_calendar(html)
    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("鈴鹿サーキット公式から今後の主要イベントを取得できませんでした。")

    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in merged),
        "hold": sum(e.get("decision") == "hold" for e in merged),
        "exclude": sum(e.get("decision") == "exclude" for e in merged),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("SUZUKA parsed", len(parsed), "future", len(found), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
