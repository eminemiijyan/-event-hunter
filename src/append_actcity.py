from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.actcity.jp"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTHS_AHEAD = 6
DETAIL_RE = re.compile(r"/event/detail/\?id=\d+")
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
EXCLUDE_WORDS = (
    "就職", "転職", "就活", "説明会", "講座", "研修", "セミナー", "ミニコンサート",
    "公開レッスン", "発表会", "定期演奏会", "練習", "リハーサル", "暴力追放", "薬物乱用",
)
MIDDLE_HALL_MAJOR = (
    "全国", "国際", "フェス", "コンクール", "オーケストラ", "ツアー", "コンサート",
    "交響楽団", "リサイタル", "プレミアム", "ジャズ", "バレエ", "ミュージカル",
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
            print(f"ACTCITY retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def month_pairs(start: date, count: int = MONTHS_AHEAD) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    for _ in range(count):
        out.append((y, m))
        m += 1
        if m == 13:
            y += 1
            m = 1
    return out


def _find_event_container(a):
    node = a
    for _ in range(7):
        node = getattr(node, "parent", None)
        if node is None:
            return None
        text = " ".join(node.get_text(" ", strip=True).split())
        if "場 所" in text and DATE_RE.search(text):
            return node
    return None


def _parse_dates(prefix: str, year: int) -> tuple[date, date] | None:
    found = DATE_RE.findall(prefix)
    if not found:
        return None
    sm, sd = map(int, found[0])
    em, ed = (map(int, found[1]) if len(found) > 1 else (sm, sd))
    sy = year
    ey = year + (1 if em < sm else 0)
    try:
        return date(sy, sm, sd), date(ey, em, ed)
    except ValueError:
        return None


def _is_target(title: str, venue: str) -> bool:
    if any(w in title for w in EXCLUDE_WORDS):
        return False
    if "大ホール" in venue or "展示イベントホール" in venue:
        return True
    if "中ホール" in venue and any(w.casefold() in title.casefold() for w in MIDDLE_HALL_MAJOR):
        return True
    return False


def parse_month(page_html: str, year: int) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        url = urljoin(BASE, href)
        if not DETAIL_RE.search(url) or url in seen:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or title in ("詳細へ", "チケット購入"):
            continue
        container = _find_event_container(a)
        if container is None:
            continue
        text = " ".join(container.get_text(" ", strip=True).split())
        idx = text.find(title)
        prefix = text[:idx] if idx >= 0 else text
        parsed_dates = _parse_dates(prefix, year)
        if not parsed_dates:
            continue
        start, end = parsed_dates
        venue_match = re.search(r"場\s*所\s*(.+?)(?:時\s*間|詳細へ|チケット)", text)
        venue = venue_match.group(1).strip() if venue_match else "アクトシティ浜松"
        if not _is_target(title, venue):
            continue
        seen.add(url)
        out.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": f"アクトシティ浜松 {venue}" if "アクトシティ" not in venue else venue,
            "prefecture": "静岡県",
            "category": "コンサート・舞台" if any(w in title for w in ("コンサート", "オーケストラ", "リサイタル", "バレエ", "ミュージカル", "合唱")) else "展示会・イベント",
            "source": "アクトシティ浜松",
            "official_url": url,
            "decision": "display",
            "decision_reason": "アクトシティ浜松公式カレンダーから大ホール・展示イベントホール等の主要催事を抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def collapse_contiguous(items: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for item in items:
        grouped.setdefault((_norm(item.get("title", "")), item.get("venue", "")), []).append(item)

    out: list[dict] = []
    for group in grouped.values():
        group.sort(key=lambda e: (e["start_date"], e["end_date"]))
        current = dict(group[0])
        for item in group[1:]:
            current_end = date.fromisoformat(current["end_date"])
            next_start = date.fromisoformat(item["start_date"])
            if next_start <= current_end + timedelta(days=1):
                current["end_date"] = max(current["end_date"], item["end_date"])
            else:
                out.append(current)
                current = dict(item)
        out.append(current)
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
    found: list[dict] = []
    reachable = 0
    for y, m in month_pairs(today):
        url = f"{BASE}/event/?ym={y}{m:02d}"
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print("ACTCITY month unavailable", type(exc).__name__, y, m)
            continue
        reachable += 1
        parsed = parse_month(html, y)
        print("ACTCITY", f"{y}-{m:02d}", "major", len(parsed))
        found.extend(e for e in parsed if e["end_date"] >= today.isoformat())
    if not reachable:
        print("ACTCITY skipped: official calendar unavailable")
        return
    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = collapse_contiguous(list(unique.values()))
    before = len(events)
    for item in found:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)
    events.sort(key=lambda e: (e.get("start_date", ""), e.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: sum(e.get("decision") == k for e in events) for k in ("display", "hold", "exclude")}
    meta.update({"updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"), "source_count": len({e.get("source") for e in events if e.get("source")}), "event_count": len(events), "decision_counts": counts})
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ACTCITY found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
