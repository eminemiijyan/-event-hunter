from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

SOURCE_URL = "https://www.aichi-koen.com/moricoro/moricoro_event/"
FALLBACK_URL = "https://www.aichi-koen.com/moricoro/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

MAJOR_WORDS = (
    "祭", "まつり", "フェス", "フェスタ", "FES", "エコアクション", "ハロウィン",
)
SKIP_WORDS = (
    "受付終了", "中止", "ボランティア募集", "ガイドツアー", "記念撮影会",
)
ISO_DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def fetch_html(url: str = SOURCE_URL, attempts: int = 2) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                url,
                timeout=(8, 20),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.9)",
                    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
                },
            )
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"MORICORO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _is_major(title: str) -> bool:
    if any(word in title for word in SKIP_WORDS):
        return False
    folded = title.casefold()
    return any(word.casefold() in folded for word in MAJOR_WORDS)


def _dates_from_block(block) -> tuple[str, str] | None:
    time_node = block.select_one("time.p-moricoro__event__list__time") or block.find("time")
    text = time_node.get_text(" ", strip=True) if time_node else " ".join(block.stripped_strings)
    found = ISO_DATE_RE.findall(text)
    if not found:
        return None
    dates = [f"{int(y):04d}-{int(m):02d}-{int(d):02d}" for y, m, d in found]
    return dates[0], dates[-1]


def _venue_from_text(text: str) -> str:
    m = re.search(
        r"(?:会場|場所)[：:]\s*(.*?)(?=\s+(?:主催|MC|時間|定員|費用|参加費|内容)[：:]|\s+※|\s+詳しく|$)",
        text,
    )
    if m:
        venue = m.group(1).strip(" ・•")
        if venue:
            if "モリコロ" in venue or "愛・地球博記念公園" in venue:
                return venue
            return f"愛・地球博記念公園（モリコロパーク） {venue}"
    if "三日月休憩所" in text:
        return "愛・地球博記念公園（モリコロパーク） 三日月休憩所"
    return "愛・地球博記念公園（モリコロパーク）"


def _official_link(block) -> str:
    for a in block.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href.startswith(("http://", "https://")):
            continue
        host = (urlparse(href).hostname or "").lower()
        if host in {"contents.file-server.net"}:
            continue
        if href.lower().endswith(".pdf"):
            continue
        return href
    return SOURCE_URL


def category_for(title: str) -> str:
    t = title.casefold()
    if any(word.casefold() in t for word in ("祭", "まつり", "フェス", "フェスタ", "ハロウィン")):
        return "祭り・季節"
    return "その他"


def parse_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    events = []
    for block in soup.select("li.p-moricoro__event__list__triger"):
        title_node = block.find("h3")
        if not title_node:
            continue
        title = title_node.get_text(" ", strip=True)
        if not title or not _is_major(title):
            continue
        dates = _dates_from_block(block)
        if not dates:
            continue
        start, end = dates
        full_text = " ".join(block.stripped_strings)
        events.append({
            "title": title,
            "start_date": start,
            "end_date": end,
            "venue": _venue_from_text(full_text),
            "prefecture": "愛知県",
            "category": category_for(title),
            "source": "モリコロパーク",
            "official_url": _official_link(block),
            "decision": "display",
            "decision_reason": "モリコロパーク公式掲載の主要イベント",
        })

    unique = {}
    for event in events:
        key = (event["title"], event["start_date"], event["end_date"])
        unique[key] = event
    return list(unique.values())


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    used_fallback = False
    try:
        html = fetch_html(SOURCE_URL)
    except requests.RequestException as primary_exc:
        print("MORICORO primary unavailable", type(primary_exc).__name__)
        try:
            html = fetch_html(FALLBACK_URL, attempts=1)
            used_fallback = True
            print("MORICORO using official homepage fallback")
        except requests.RequestException as fallback_exc:
            print("MORICORO skipped: official sources unavailable", type(fallback_exc).__name__)
            return

    found = [e for e in parse_events(html) if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("モリコロパークの主要イベントを取得できませんでした。")

    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in merged),
        "hold": sum(e.get("decision") == "hold" for e in merged),
        "exclude": sum(e.get("decision") == "exclude" for e in merged),
    }
    if used_fallback:
        meta.setdefault("degraded_sources", {})["モリコロパーク"] = (
            "イベント専用ページ取得失敗のため同一公式サイトのトップページを使用"
        )
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MORICORO found", len(found), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
