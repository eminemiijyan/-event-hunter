from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.yaizu.gr.jp"
CATEGORY_URL = f"{BASE}/news_category/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTH_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月")
JP_DATE_RE = re.compile(r"(?:(20\d{2})\s*年)?\s*(?:(\d{1,2})\s*月)?\s*(\d{1,2})\s*日")

TARGET_PHRASES = (
    "おおいがわフェア",
    "夏のあかり展",
    "魚(とと)フェス",
    "魚（とと）フェス",
    "焼津超大漁祭",
    "焼津ライトアップ・イルミネーション",
    "焼津さかなセンター祭り",
    "国際交流フェスタ",
    "特別展",
    "おおいがわ街道カーニバル",
    "クリスマスマーケット",
    "焼津カツオSHOWてん",
    "焼津海上花火大会",
)


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                url,
                timeout=(10, 45),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                    "Accept-Language": "ja-JP,ja;q=0.9",
                },
            )
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"YAIZU_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _is_target(title: str) -> bool:
    folded = unicodedata.normalize("NFKC", title).casefold()
    return any(unicodedata.normalize("NFKC", phrase).casefold() in folded for phrase in TARGET_PHRASES)


def _month_index(year: int, month: int) -> int:
    return year * 12 + month - 1


def discover_monthly_pages(category_html: str, today: date) -> list[tuple[int, int, str]]:
    soup = BeautifulSoup(category_html, "html.parser")
    current = _month_index(today.year, today.month)
    last = current + 5
    out: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = _clean(a.get_text(" ", strip=True))
        m = MONTH_RE.search(text)
        if not m or not any(word in text for word in ("イベント", "行事")):
            continue
        year, month = int(m.group(1)), int(m.group(2))
        if not 1 <= month <= 12 or not current <= _month_index(year, month) <= last:
            continue
        url = urljoin(CATEGORY_URL, a["href"])
        parsed = urlparse(url)
        if parsed.netloc not in ("yaizu.gr.jp", "www.yaizu.gr.jp") or not parsed.path.startswith("/news/"):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((year, month, url))
    return sorted(out)


def parse_dates(text: str, default_year: int, default_month: int) -> tuple[date, date] | None:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = re.split(r"(?:予備日|※当初日程)", normalized, maxsplit=1)[0]
    matches = list(JP_DATE_RE.finditer(normalized))
    if not matches:
        return None
    values: list[date] = []
    current_year, current_month = default_year, default_month
    for m in matches:
        if m.group(1):
            current_year = int(m.group(1))
        if m.group(2):
            next_month = int(m.group(2))
            if not m.group(1) and next_month < current_month and current_month >= 10:
                current_year += 1
            current_month = next_month
        try:
            values.append(date(current_year, current_month, int(m.group(3))))
        except ValueError:
            continue
    if not values:
        return None
    return values[0], values[-1]


def _line_after_label(line: str, label: str) -> str:
    text = _clean(line)
    if not text.startswith(label):
        return ""
    return text[len(label):].lstrip(" |｜:：")


def _find_title(lines: list[str], index: int) -> str | None:
    for pos in range(index - 1, max(-1, index - 6), -1):
        line = lines[pos]
        if not line or line.startswith(("※", "場所", "関連リンク", "問合せ", "お問い合わせ")):
            continue
        if re.search(r"https?://", line) or JP_DATE_RE.search(line):
            continue
        return line
    return None


def _find_venue(lines: list[str], start_index: int) -> str:
    for pos in range(start_index + 1, min(len(lines), start_index + 9)):
        line = lines[pos]
        if line.startswith("開催期間"):
            break
        if not line.startswith("場所"):
            continue
        value = _line_after_label(line, "場所")
        next_pos = pos + 1
        if not value and next_pos < len(lines):
            value = lines[next_pos]
            next_pos += 1
        continuations: list[str] = []
        while next_pos < min(len(lines), pos + 5):
            nxt = lines[next_pos]
            if nxt.startswith(("関連リンク", "問合せ", "お問い合わせ", "開催期間", "※")):
                break
            if nxt and not _is_target(nxt):
                continuations.append(nxt)
            next_pos += 1
        venue = " ".join([value, *continuations]).strip()
        return venue[:160] if venue else "焼津市"
    return "焼津市"


def category_for(title: str) -> str:
    if "特別展" in title:
        return "展示会"
    if any(word in title for word in ("魚", "さかな", "カツオ", "クリスマスマーケット")):
        return "グルメ"
    return "祭り・季節"


def parse_events(page_html: str, page_url: str, article_year: int, article_month: int, today: date) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [_clean(line) for line in soup.get_text("\n", strip=True).splitlines()]
    lines = [line for line in lines if line]
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, line in enumerate(lines):
        if not line.startswith("開催期間"):
            continue
        title = _find_title(lines, i)
        if not title or not _is_target(title):
            continue

        date_parts: list[str] = []
        inline = _line_after_label(line, "開催期間")
        if inline:
            date_parts.append(inline)
        for pos in range(i + 1, min(len(lines), i + 5)):
            nxt = lines[pos]
            if nxt.startswith("場所"):
                break
            if nxt.startswith("※"):
                continue
            if JP_DATE_RE.search(nxt):
                date_parts.append(nxt)
        dates = parse_dates(" ".join(date_parts), article_year, article_month)
        if not dates:
            continue
        start, end = dates
        if end < today:
            continue
        venue = _find_venue(lines, i)
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
            "source": "焼津市観光協会",
            "official_url": page_url,
            "decision": "display",
            "decision_reason": "焼津市観光協会公式の月別イベント情報から大規模・季節イベントを抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "静岡県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a, b = _norm(existing.get("title", "")), _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        category_html = fetch_html(CATEGORY_URL)
    except requests.RequestException as exc:
        print("YAIZU_KANKO skipped: official event archive unavailable", type(exc).__name__)
        return

    pages = discover_monthly_pages(category_html, today)
    found: list[dict] = []
    failed_pages = 0
    for year, month, url in pages:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException:
            failed_pages += 1
            continue
        found.extend(parse_events(html, url, year, month, today))

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = sorted(unique.values(), key=lambda e: (e["start_date"], e["title"]))

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
    print("YAIZU_KANKO pages", len(pages), "found", len(found), "added", len(events) - before, "failed_pages", failed_pages)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
