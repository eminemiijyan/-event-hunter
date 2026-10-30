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
EVENT_RE = re.compile(r"〖([^〗]+)〗")


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
            # 岐阜市公式サイトはUTF-8のため、環境ごとの推定差を避ける。
            r.encoding = "utf-8"
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


def _venue_before(text: str, marker_start: int) -> str:
    before = text[:marker_start]
    lines = [line.strip() for line in before.splitlines() if line.strip()]
    if not lines:
        return "岐阜市内公園"
    venue = lines[-1]
    if len(venue) > 100 or "開催日" in venue or "大型イベント" in venue:
        return "岐阜市内公園"
    return venue


def parse_events(page_html: str, base_year: int) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    visible = "\n".join(" ".join(s.split()) for s in soup.stripped_strings)

    # 岐阜市が「大型イベント」と明記した区間だけを対象にする。
    section_pos = visible.find("その他の公園の大型イベント")
    if section_pos >= 0:
        visible = visible[section_pos + len("その他の公園の大型イベント"):]
    for stop_word in ("このページに関するお問い合わせ", "より良いホームページ"):
        stop = visible.find(stop_word)
        if stop >= 0:
            visible = visible[:stop]

    matches = list(EVENT_RE.finditer(visible))
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for idx, match in enumerate(matches):
        title = " ".join(match.group(1).split())
        if not title:
            continue
        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(visible)
        body = visible[match.end():next_start]
        dates = _parse_date_block(body, base_year)
        if not dates:
            continue
        start_date, end_date = dates
        key = (title, start_date.isoformat())
        if key in seen:
            continue
        out.append({
            "title": title,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "venue": _venue_before(visible, match.start()),
            "prefecture": "岐阜県",
            "category": category_for(title),
            "source": "岐阜市公園イベント",
            "official_url": URL,
            "decision": "display",
            "decision_reason": "岐阜市公式が大型イベントとして掲載",
        })
        seen.add(key)
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

    parsed = parse_events(html, today.year)
    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        visible = " ".join(BeautifulSoup(html, "html.parser").stripped_strings)
        print(
            "GIFU_PARKS debug",
            "html_len", len(html),
            "parsed", len(parsed),
            "has_title", "岐阜市内公園のイベント情報" in visible,
            "has_section", "その他の公園の大型イベント" in visible,
            "has_brackets", "〖" in visible and "〗" in visible,
            "has_date", bool(DATE_RE.search(visible)),
        )
        print("GIFU_PARKS skipped: no future exact-date events parsed")
        return

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

    print("GIFU_PARKS parsed", len(parsed), "found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
