from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

LIST_URL = "https://www.nagashima-onsen.co.jp/spaland/info/index.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
ALLOWED_HOST = "www.nagashima-onsen.co.jp"

# Event Hunter向けの「わざわざ出掛ける候補」に絞る。
# 割引券や年間パスなどの販売施策は、ここに該当しないため取得しない。
MAJOR_TITLE_WORDS = (
    "逃走中",
    "ハロウィン",
    "ゾンビ",
    "花火",
    "フィッシャーズ",
    "ワンワン",
    "クリスマス",
    "カウントダウン",
    "フェス",
    "ステージイベント",
    "ショー",
)

JP_RANGE_RE = re.compile(
    r"(?:(?P<sy>20\d{2})年)?\s*(?P<sm>\d{1,2})月\s*(?P<sd>\d{1,2})日"
    r"(?:（[^）]*）|\([^)]*\))?\s*[～〜~\-–—]\s*"
    r"(?:(?P<ey>20\d{2})年)?\s*(?P<em>\d{1,2})月\s*(?P<ed>\d{1,2})日"
)
SLASH_RANGE_RE = re.compile(
    r"(?:(?P<sy>20\d{2})[./年])?\s*(?P<sm>\d{1,2})[./月]\s*(?P<sd>\d{1,2})(?:日)?"
    r"(?:（[^）]*）|\([^)]*\))?\s*[～〜~\-–—]\s*"
    r"(?:(?P<ey>20\d{2})[./年])?\s*(?P<em>\d{1,2})[./月]\s*(?P<ed>\d{1,2})(?:日)?"
)
JP_SINGLE_RE = re.compile(r"(?:(?P<y>20\d{2})年)?\s*(?P<m>\d{1,2})月\s*(?P<d>\d{1,2})日")
SLASH_SINGLE_RE = re.compile(r"(?:(?P<y>20\d{2})[./])(?P<m>\d{1,2})[./](?P<d>\d{1,2})")
PUBLISHED_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")


def fetch_html(url: str, attempts: int = 3) -> str:
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
            print(f"NAGASHIMA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _is_major_title(title: str) -> bool:
    folded = title.casefold()
    return any(word.casefold() in folded for word in MAJOR_TITLE_WORDS)


def discover_articles(list_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(list_html, "html.parser")
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        if not title or not _is_major_title(title):
            continue
        url = urljoin(LIST_URL, a["href"])
        parsed = urlparse(url)
        if parsed.netloc != ALLOWED_HOST:
            # 主催者外部サイトへ直接飛ぶ告知は、この情報源では無理に取り込まない。
            continue
        if "/spaland/info/" not in parsed.path or parsed.path.endswith("/info/index.html"):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append((title, url))
    return out


def _make_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date_span(text: str, default_year: int) -> tuple[date, date] | None:
    text = " ".join(text.split())
    for regex in (JP_RANGE_RE, SLASH_RANGE_RE):
        m = regex.search(text)
        if not m:
            continue
        sy = int(m.group("sy") or default_year)
        sm, sd = int(m.group("sm")), int(m.group("sd"))
        em, ed = int(m.group("em")), int(m.group("ed"))
        ey = int(m.group("ey")) if m.group("ey") else sy + (1 if em < sm else 0)
        start = _make_date(sy, sm, sd)
        end = _make_date(ey, em, ed)
        if start and end:
            return start, end

    m = SLASH_SINGLE_RE.search(text)
    if m:
        value = _make_date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        if value:
            return value, value

    m = JP_SINGLE_RE.search(text)
    if m:
        value = _make_date(int(m.group("y") or default_year), int(m.group("m")), int(m.group("d")))
        if value:
            return value, value
    return None


def _event_date(lines: list[str], default_year: int) -> tuple[date, date] | None:
    # 開催情報の明示行を最優先する。記事公開日をイベント日と誤認しないため。
    markers = ("開催日時", "開催期間", "開催日")
    for i, line in enumerate(lines):
        if not any(marker in line for marker in markers):
            continue
        text = " ".join(lines[i:min(i + 3, len(lines))])
        dates = parse_date_span(text, default_year)
        if dates:
            return dates

    # ハロウィン等、「開催期間：10/1～11/3」のような表記も拾う。
    for i, line in enumerate(lines[:45]):
        if "開催" not in line and "期間" not in line:
            continue
        text = " ".join(lines[i:min(i + 3, len(lines))])
        dates = parse_date_span(text, default_year)
        if dates:
            return dates

    return None


def category_for(title: str) -> str:
    if any(w in title for w in ("ハロウィン", "ゾンビ", "花火", "クリスマス", "カウントダウン", "フェス")):
        return "祭り・季節"
    if any(w in title for w in ("フィッシャーズ", "ワンワン", "ステージ", "ショー")):
        return "コンサート・ショー"
    return "その他"


def parse_article(page_html: str, url: str, fallback_title: str = "") -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    h1 = soup.find("h1")
    title = " ".join((h1.get_text(" ", strip=True) if h1 else fallback_title).split())
    if not title or not _is_major_title(title):
        return None

    lines = [" ".join(s.split()) for s in soup.stripped_strings]
    published_year = datetime.now(ZoneInfo("Asia/Tokyo")).year
    for line in lines[:12]:
        m = PUBLISHED_RE.fullmatch(line)
        if m:
            published_year = int(m.group(1))
            break

    dates = _event_date(lines, published_year)
    if not dates:
        return None
    start, end = dates

    return {
        "title": title,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": "ナガシマスパーランド",
        "prefecture": "三重県",
        "category": category_for(title),
        "source": "ナガシマスパーランド",
        "official_url": url,
        "decision": "display",
        "decision_reason": "ナガシマスパーランド公式が告知する大型・集客イベント",
    }


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        listing = fetch_html(LIST_URL)
    except requests.RequestException as exc:
        print("NAGASHIMA skipped: listing unavailable", type(exc).__name__)
        return

    articles = discover_articles(listing)
    if not articles:
        raise RuntimeError("ナガシマスパーランド公式のお知らせから対象記事を確認できませんでした。")

    found: list[dict] = []
    failed_details = 0
    for fallback_title, url in articles:
        try:
            html = fetch_html(url)
        except requests.RequestException:
            failed_details += 1
            continue
        event = parse_article(html, url, fallback_title)
        if event and event["end_date"] >= today.isoformat():
            found.append(event)

    # 詳細取得に一部失敗しても「イベントなし」扱いにしない。
    if not found:
        if failed_details:
            print("NAGASHIMA skipped: detail pages unavailable", failed_details)
            return
        raise RuntimeError("ナガシマスパーランド公式から今後の大型イベントを取得できませんでした。")

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

    print(
        "NAGASHIMA articles", len(articles),
        "future", len(found),
        "failed_details", failed_details,
        "added", len(merged) - before,
    )
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
