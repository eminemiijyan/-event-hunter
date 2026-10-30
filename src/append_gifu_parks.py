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

URL = "https://www.city.gifu.lg.jp/info/machizukuri/1007994/1035968/index.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_RE = re.compile(r"(?:(20\d{2})年)?\s*(\d{1,2})月\s*(\d{1,2})日")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 45), headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
                "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"GIFU_PARKS retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("酒祭", "麦酒", "グルメ", "フード", "ビール")):
        return "グルメ"
    if any(w in t for w in ("花火", "まつり", "祭", "フェスティバル", "菊花")):
        return "祭り・季節"
    if any(w in t for w in ("マラソン", "スポレク", "スポーツ")):
        return "スポーツ"
    if any(w in t for w in ("コンサート", "jazz", "薪能", "猿まわし")):
        return "コンサート・ショー"
    return "その他"


def _parse_date_block(text: str, base_year: int) -> tuple[date, date] | None:
    values: list[date] = []
    for year_text, month_text, day_text in DATE_RE.findall(text):
        year = int(year_text) if year_text else base_year
        try:
            values.append(date(year, int(month_text), int(day_text)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values), max(values)


def _event_title(line: str) -> tuple[str, str] | None:
    if "〖" not in line or "〗" not in line:
        return None
    before, rest = line.split("〖", 1)
    title, _ = rest.split("〗", 1)
    title = title.strip()
    if not title:
        return None
    return before.strip(), title


def parse_events(page_html: str, base_year: int) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [" ".join(s.split()) for s in soup.stripped_strings]

    # Only parse the official section explicitly labelled as major park events.
    start = 0
    for idx, line in enumerate(lines):
        if "その他の公園の大型イベント" in line:
            start = idx + 1
            break

    end = len(lines)
    for idx in range(start, len(lines)):
        if "より良いホームページ" in lines[idx] or "このページに関するお問い合わせ" in lines[idx]:
            end = idx
            break
    lines = lines[start:end]

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    i = 0
    while i < len(lines):
        parsed = _event_title(lines[i])
        if not parsed:
            i += 1
            continue

        venue, title = parsed
        if not venue and i > 0:
            previous = lines[i - 1].strip()
            if "開催日" not in previous and "〖" not in previous:
                venue = previous

        block: list[str] = []
        j = i + 1
        while j < len(lines) and _event_title(lines[j]) is None and len(block) < 12:
            block.append(lines[j])
            j += 1

        # Some events list the second day on a separate line, so parse all
        # explicit M月D日 values until the next event title.
        date_text = " ".join(block)
        dates = _parse_date_block(date_text, base_year)
        if dates:
            start_date, end_date = dates
            key = (title, start_date.isoformat())
            if key not in seen:
                out.append({
                    "title": title,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "venue": venue or "岐阜市内公園",
                    "prefecture": "岐阜県",
                    "category": category_for(title),
                    "source": "岐阜市公園イベント",
                    "official_url": URL,
                    "decision": "display",
                    "decision_reason": "岐阜市公式が大型イベントとして掲載",
                })
                seen.add(key)
        i = j
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[\s\-‐‑–—・･:：/／()（）\[\]【】]+", "", s)


def _overlaps(a: dict, b: dict) -> bool:
    return a.get("end_date", "") >= b.get("start_date", "") and b.get("end_date", "") >= a.get("start_date", "")


def append_events(events: list[dict], new_events: list[dict]) -> list[dict]:
    out = list(events)
    for item in new_events:
        if any(_norm(e.get("title", "")) == _norm(item["title"]) and _overlaps(e, item) for e in out):
            continue
        out.append(item)
    return sorted(out, key=lambda e: (e.get("start_date", ""), e.get("title", "")))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html(URL)
    except requests.RequestException as exc:
        print("GIFU_PARKS skipped: source unavailable", type(exc).__name__)
        return

    found = [e for e in parse_events(html, today.year) if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("岐阜市公式の公園大型イベントを取得できませんでした。")

    before = len(events)
    events = append_events(events, found)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in events),
        "hold": sum(e.get("decision") == "hold" for e in events),
        "exclude": sum(e.get("decision") == "exclude" for e in events),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("GIFU_PARKS found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
