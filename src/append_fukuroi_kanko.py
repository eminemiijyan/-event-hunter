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

BASE = "https://www.fukuroi-kankou.jp"
LIST_URL = f"{BASE}/news/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
TARGET_WORDS = (
    "祭", "まつり", "フェス", "FES", "ランタン", "夜市", "花火", "マラソン",
    "ライトアップ", "イルミ", "もみじ", "風鈴",
)
EXCLUDE_WORDS = (
    "出店します", "開催しました", "募集", "キャンペーン", "エコパ", "運行", "お越しの皆さま",
    "体験バスツアー", "情報", "観覧",
)
LIST_TEXT_RE = re.compile(r"^(?:20\d{2}\.\d{1,2}\.\d{1,2})?\s*(.+)$")
JP_DATE_RE = re.compile(r"(?:(20\d{2})年|令和\s*(\d{1,2})年)?\s*(\d{1,2})月\s*(\d{1,2})日")


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
            print(f"FUKUROI_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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


def discover_articles(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(BASE, a.get("href", "").strip())
        parsed = urlparse(url)
        if parsed.netloc not in ("fukuroi-kankou.jp", "www.fukuroi-kankou.jp"):
            continue
        if not parsed.path.startswith("/news/") or parsed.path.rstrip("/") == "/news":
            continue
        text = unicodedata.normalize("NFKC", " ".join(a.get_text(" ", strip=True).split()))
        m = LIST_TEXT_RE.match(text)
        title = (m.group(1) if m else text).strip()
        if not title or not _is_target(title) or url in seen:
            continue
        seen.add(url)
        out.append((title, url))
    return out


def _event_year(month: int, today: date) -> int:
    return today.year + (1 if today.month >= 10 and month <= 3 else 0)


def _year_from_match(gregorian: str | None, reiwa: str | None, month: int, today: date) -> int:
    if gregorian:
        return int(gregorian)
    if reiwa:
        return 2018 + int(reiwa)
    return _event_year(month, today)


def parse_detail_dates(page_html: str, today: date) -> tuple[date, date] | None:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [unicodedata.normalize("NFKC", " ".join(line.split())) for line in soup.get_text("\n", strip=True).splitlines()]
    candidates: list[str] = []
    for i, line in enumerate(lines):
        if any(label in line for label in ("開催日", "開催日時", "日時", "日程", "とき")):
            candidates.append(line)
            if i + 1 < len(lines):
                candidates.append(lines[i + 1])
    candidates.extend(line for line in lines if re.search(r"20\d{2}年\s*\d{1,2}月\s*\d{1,2}日", line))
    for candidate in candidates:
        matches = list(JP_DATE_RE.finditer(candidate))
        if not matches:
            continue
        first = matches[0]
        sm, sd = int(first.group(3)), int(first.group(4))
        sy = _year_from_match(first.group(1), first.group(2), sm, today)
        second = matches[1] if len(matches) > 1 else None
        if second:
            em, ed = int(second.group(3)), int(second.group(4))
            ey = _year_from_match(second.group(1), second.group(2), em, today)
            if not second.group(1) and not second.group(2) and em < sm:
                ey = sy + 1
        else:
            em, ed, ey = sm, sd, sy
        try:
            return date(sy, sm, sd), date(ey, em, ed)
        except ValueError:
            continue
    return None


def parse_detail_venue(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [unicodedata.normalize("NFKC", " ".join(line.split())) for line in soup.get_text("\n", strip=True).splitlines()]
    for i, line in enumerate(lines):
        m = re.search(r"(?:場所|会場)[：:\s]*(.+)$", line)
        if m and m.group(1).strip():
            return m.group(1).strip(" ・、。")
        if line.rstrip("：:") in ("場所", "会場") and i + 1 < len(lines):
            value = lines[i + 1].strip()
            if value:
                return value
    return None


def category_for(title: str) -> str:
    if "花火" in title:
        return "花火"
    if "マラソン" in title:
        return "スポーツ"
    return "祭り・季節"


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
        listing = fetch_html(LIST_URL)
    except requests.RequestException as exc:
        print("FUKUROI_KANKO skipped: official news listing unavailable", type(exc).__name__)
        return

    articles = discover_articles(listing)
    found: list[dict] = []
    failed_details = 0
    for title, url in articles[:30]:
        try:
            detail = fetch_html(url, attempts=2)
        except requests.RequestException:
            failed_details += 1
            continue
        dates = parse_detail_dates(detail, today)
        if dates is None:
            continue
        start, end = dates
        if end < today:
            continue
        found.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": parse_detail_venue(detail) or "袋井市",
            "prefecture": "静岡県",
            "category": category_for(title),
            "source": "袋井市観光協会",
            "official_url": url,
            "decision": "display",
            "decision_reason": "袋井市観光協会公式ニュースから主要な祭・フェス・季節イベントを抽出し詳細ページの日付を確認",
        })

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = list(unique.values())

    before = len(events)
    for item in sorted(found, key=lambda e: (e["start_date"], e["title"])):
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
    print("FUKUROI_KANKO articles", len(articles), "future", len(found), "added", len(events) - before, "failed_details", failed_details)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
