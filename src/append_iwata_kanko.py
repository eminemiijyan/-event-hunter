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

BASE = "https://kanko-iwata.jp"
LIST_URL = f"{BASE}/info/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
TARGET_WORDS = (
    "祭", "まつり", "フェス", "FES", "花火", "イルミ", "ライトアップ", "マラソン",
    "軽トラ市", "音楽体験", "ピアノ", "サイエンスフェスタ", "夏祭", "大名行列",
)
EXCLUDE_WORDS = (
    "ガイドウォーク", "見付宿を歩く", "教室", "講座", "募集", "セミナー", "説明会",
    "VIPルーム", "宿泊", "キャンペーン", "フォトコンテスト", "企画展", "ランナー必見",
)
TITLE_DATE_RE = re.compile(
    r"(?<!\d)(\d{1,2})/(\d{1,2})"
    r"(?:\s*[～〜~\-]\s*(?:(\d{1,2})/)?(\d{1,2})|\s*[・,，、]\s*(\d{1,2}))?"
)
LEADING_TITLE_DATE_RE = re.compile(
    r"^\s*\d{1,2}/\d{1,2}"
    r"(?:\s*[～〜~\-]\s*(?:\d{1,2}/)?\d{1,2}|\s*[・,，、]\s*\d{1,2})?\s*"
)
JP_DATE_RE = re.compile(r"(?:(20\d{2})年|令和\s*(\d{1,2})年)?\s*(\d{1,2})月\s*(\d{1,2})日")
DAY_ONLY_END_RE = re.compile(r"(?:[・,，、]|[～〜~\-])\s*(\d{1,2})日")


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
            print(f"IWATA_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _clean_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", " ".join(title.split()))
    return LEADING_TITLE_DATE_RE.sub("", text).strip()


def _is_target(title: str) -> bool:
    if any(w.casefold() in title.casefold() for w in EXCLUDE_WORDS):
        return False
    return any(w.casefold() in title.casefold() for w in TARGET_WORDS)


def discover_articles(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        a = heading.find("a", href=True)
        if not a:
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or not _is_target(title):
            continue
        url = urljoin(BASE, a["href"])
        parsed = urlparse(url)
        if parsed.netloc not in ("kanko-iwata.jp", "www.kanko-iwata.jp") or url in seen:
            continue
        seen.add(url)
        out.append((title, url))
    return out


def _event_year(month: int, today: date) -> int:
    return today.year + (1 if today.month >= 10 and month <= 3 else 0)


def parse_title_dates(title: str, today: date) -> tuple[date, date] | None:
    text = unicodedata.normalize("NFKC", title)
    m = TITLE_DATE_RE.search(text)
    if not m:
        return None
    sm, sd = int(m.group(1)), int(m.group(2))
    em = int(m.group(3) or sm)
    ed = int(m.group(4) or m.group(5) or sd)
    sy = _event_year(sm, today)
    ey = sy + (1 if em < sm else 0)
    try:
        return date(sy, sm, sd), date(ey, em, ed)
    except ValueError:
        return None


def _year_from_match(gregorian: str | None, reiwa: str | None, month: int, today: date) -> int:
    if gregorian:
        return int(gregorian)
    if reiwa:
        return 2018 + int(reiwa)
    return _event_year(month, today)


def _date_candidates(page_html: str) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [unicodedata.normalize("NFKC", " ".join(line.split())) for line in soup.get_text("\n", strip=True).splitlines()]
    candidates: list[str] = []
    for i, line in enumerate(lines):
        if re.search(r"(?:開催日(?:時)?|日時|日程|点灯期間|とき)", line):
            candidates.append(line)
            if i + 1 < len(lines):
                candidates.append(f"{line} {lines[i + 1]}")
    return candidates or lines


def parse_detail_dates(page_html: str, today: date) -> tuple[date, date] | None:
    for candidate in _date_candidates(page_html):
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
            tail = candidate[first.end():]
            day_only = DAY_ONLY_END_RE.search(tail)
            if day_only:
                em, ed, ey = sm, int(day_only.group(1)), sy
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
        m = re.search(r"(?:開催場所|会場|場所)[◆：:\s]*(.+)$", line)
        if m and m.group(1).strip():
            venue = m.group(1).strip(" ・、。")
            return venue or None
        if line.rstrip("◆：:") in ("開催場所", "会場", "場所") and i + 1 < len(lines):
            venue = lines[i + 1].strip(" ・、。")
            if venue:
                return venue
    return None


def _fallback_venue_from_title(title: str) -> str:
    clean = _clean_title(title)
    if "磐田駅北口多目的広場" in clean:
        return "磐田駅北口多目的広場"
    return "磐田市"


def category_for(title: str) -> str:
    if any(w in title for w in ("祭", "まつり", "フェス", "FES", "花火", "イルミ", "ライトアップ")):
        return "祭り・季節"
    if "マラソン" in title:
        return "スポーツ"
    if any(w in title for w in ("音楽", "ピアノ", "コンサート")):
        return "コンサート・舞台"
    return "その他"


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
        print("IWATA_KANKO skipped: official listing unavailable", type(exc).__name__)
        return

    articles = discover_articles(listing)
    found: list[dict] = []
    failed_details = 0
    for title, url in articles[:30]:
        dates = parse_title_dates(title, today)
        venue = _fallback_venue_from_title(title)
        detail = None
        try:
            detail = fetch_html(url, attempts=2)
        except requests.RequestException:
            failed_details += 1
        if dates is None and detail:
            dates = parse_detail_dates(detail, today)
        if dates is None:
            continue
        if detail:
            venue = parse_detail_venue(detail) or venue
        start, end = dates
        if end < today:
            continue
        clean_title = _clean_title(title)
        found.append({
            "title": clean_title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": venue,
            "prefecture": "静岡県",
            "category": category_for(clean_title),
            "source": "磐田市観光協会",
            "official_url": url,
            "decision": "display",
            "decision_reason": "磐田市観光協会公式の新着情報から主要な祭・フェス・季節・大型体験イベントを抽出",
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
    print("IWATA_KANKO articles", len(articles), "future", len(found), "added", len(events) - before, "failed_details", failed_details)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
