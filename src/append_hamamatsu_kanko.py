from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://hamamatsu-daisuki.net"
ARCHIVE_URL = f"{BASE}/information/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTH_ARTICLE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月イベント情報")
DATE_RE = re.compile(r"(\d{1,2})月(\d{1,2})日(?:\s*[〜～~\-]\s*(?:(\d{1,2})月)?(\d{1,2})日)?")
TARGET_WORDS = (
    "祭", "まつり", "フェス", "FES", "フェスタ", "花火", "マルシェ", "イルミ",
    "ライトアップ", "産業祭", "文化祭", "大会", "博", "フェア", "家康公", "ツーリングラリー",
)
EXCLUDE_WORDS = (
    "教室", "講座", "散歩", "観望", "撮影", "ワークショップ", "セミナー", "募集", "フォトコンテスト",
    "アクトシティ", "エコパ", "宿泊", "キャンペーン", "マスターコース", "プラネタリウム",
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
            print(f"HAMAMATSU_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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


def discover_month_articles(page_html: str) -> list[tuple[str, int, int]]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        m = MONTH_ARTICLE_RE.search(text)
        if not m:
            continue
        url = urljoin(BASE, a["href"])
        if url in seen:
            continue
        seen.add(url)
        out.append((url, int(m.group(1)), int(m.group(2))))
    return out


def _section_text(heading) -> str:
    chunks: list[str] = []
    for node in heading.next_siblings:
        name = getattr(node, "name", None)
        if name in ("h2", "h3"):
            break
        if hasattr(node, "get_text"):
            text = " ".join(node.get_text(" ", strip=True).split())
        else:
            text = " ".join(str(node).split())
        if text:
            chunks.append(text)
    return " ".join(chunks)


def parse_month_article(page_html: str, year: int, month: int, url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for heading in soup.find_all(["h2", "h3"]):
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title or not _is_target(title):
            continue
        section = _section_text(heading)
        m = DATE_RE.search(section)
        if not m:
            continue
        sm, sd = int(m.group(1)), int(m.group(2))
        em = int(m.group(3) or sm)
        ed = int(m.group(4) or sd)
        sy = year + (1 if month >= 10 and sm <= 3 else 0)
        ey = sy + (1 if em < sm else 0)
        try:
            start = date(sy, sm, sd)
            end = date(ey, em, ed)
        except ValueError:
            continue
        key = (_norm(title), start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        venue_match = re.search(r"📍\s*(.+)$", section)
        venue = venue_match.group(1).strip() if venue_match else "浜松市・浜名湖エリア"
        out.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": venue,
            "prefecture": "静岡県",
            "category": "祭り・季節" if any(w in title for w in ("祭", "まつり", "フェス", "FES", "フェスタ", "花火", "イルミ", "ライトアップ")) else "その他",
            "source": "浜松・浜名湖だいすきネット",
            "official_url": url,
            "decision": "display",
            "decision_reason": "浜松・浜名湖公式観光サイトの月間イベント情報から主要イベントを抽出",
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
        archive = fetch_html(ARCHIVE_URL)
    except requests.RequestException as exc:
        print("HAMAMATSU_KANKO skipped: official archive unavailable", type(exc).__name__)
        return

    articles = discover_month_articles(archive)
    found: list[dict] = []
    failed = 0
    for url, y, m in articles[:3]:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException:
            failed += 1
            continue
        parsed = parse_month_article(html, y, m, url)
        print("HAMAMATSU_KANKO", f"{y}-{m:02d}", "targets", len(parsed))
        found.extend(e for e in parsed if e["end_date"] >= today.isoformat())

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
    print("HAMAMATSU_KANKO articles", len(articles), "found", len(found), "added", len(events) - before, "failed", failed)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
