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

BASE = "https://www.kanko-shima.com"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTHS_AHEAD = 6
DETAIL_PATH_RE = re.compile(r"^/event/\d+/?$")
DATE_RE = re.compile(
    r"(20\d{2})\.(\d{1,2})\.(\d{1,2})\s*\([^)]*\)\s*[〜～~\-]\s*"
    r"(20\d{2})\.(\d{1,2})\.(\d{1,2})"
)
LEADING_TAG_RE = re.compile(r"^(?:[【〖][^】〗]+[】〗]\s*)+")
TARGET_WORDS = (
    "祭", "まつり", "フェス", "FES", "フェスタ", "MARCHE", "マルシェ", "花火",
    "ライトアップ", "イルミ", "灯台", "サイクリング", "マラソン", "大会", "オータムキャンペーン",
    "観光農園",
)
EXCLUDE_WORDS = (
    "志摩スペイン村", "Instagram", "インスタ", "SNS", "投稿キャンペーン", "フォトコンテスト",
    "ランチ", "ディナー", "会席", "アフタヌーンティー", "宿泊", "デイキャンプ", "ホテル",
    "グランドメルキュール", "志摩観光ホテル", "割引", "パスポート", "じゃらん", "スカイショット",
    "マーメイドロード", "紅葉鯛", "募集", "講演", "セミナー", "説明会", "ライドシェア",
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
                    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
                },
            )
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"SHIMA_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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


def _is_target(title: str) -> bool:
    if any(word in title for word in EXCLUDE_WORDS):
        return False
    return any(word.casefold() in title.casefold() for word in TARGET_WORDS)


def category_for(title: str) -> str:
    if any(w in title for w in ("花火", "祭", "まつり", "フェス", "FES", "フェスタ", "ライトアップ", "イルミ", "灯台")):
        return "祭り・季節"
    if any(w in title for w in ("サイクリング", "マラソン", "大会")):
        return "スポーツ"
    if any(w in title for w in ("MARCHE", "マルシェ")):
        return "グルメ"
    if any(w in title for w in ("観光農園", "オータムキャンペーン")):
        return "その他"
    return "その他"


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(BASE, a.get("href", "").strip())
        if not DETAIL_PATH_RE.match(urlparse(url).path):
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        normalized = unicodedata.normalize("NFKC", text)
        m = DATE_RE.search(normalized)
        if not m:
            continue
        title = LEADING_TAG_RE.sub("", normalized[: m.start()].strip()).strip()
        if not title or not _is_target(title):
            continue
        try:
            start = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            end = date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            continue
        key = (_norm(title), start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": "志摩市",
            "prefecture": "三重県",
            "category": category_for(title),
            "source": "志摩市観光協会",
            "official_url": url,
            "decision": "display",
            "decision_reason": "志摩市観光協会公式の月別イベント掲載から主要な祭・季節・スポーツ・家族向けイベントを抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def parse_detail_venue(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    for node in soup.find_all(["th", "dt", "h2", "h3", "h4"]):
        label = " ".join(node.get_text(" ", strip=True).split())
        if label not in ("場所", "会場", "開催場所"):
            continue
        if node.name == "th":
            value_node = node.find_next_sibling("td")
        elif node.name == "dt":
            value_node = node.find_next_sibling("dd")
        else:
            value_node = node.find_next_sibling()
        if value_node:
            value = " ".join(value_node.get_text(" ", strip=True).split())
            if value:
                return value
    return None


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "三重県" or existing.get("start_date") != candidate.get("start_date"):
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
        url = f"{BASE}/event/?s_month={m}&s_year={y}"
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print("SHIMA_KANKO month unavailable", type(exc).__name__, y, m)
            continue
        reachable += 1
        parsed = parse_listing(html)
        print("SHIMA_KANKO", f"{y}-{m:02d}", "targets", len(parsed))
        found.extend(e for e in parsed if e["end_date"] >= today.isoformat())

    if not reachable:
        print("SHIMA_KANKO skipped: official monthly pages unavailable")
        return

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = list(unique.values())

    failed_details = 0
    for item in found:
        try:
            detail = fetch_html(item["official_url"], attempts=2)
            venue = parse_detail_venue(detail)
            if venue:
                item["venue"] = venue
        except requests.RequestException:
            failed_details += 1

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
    print("SHIMA_KANKO found", len(found), "added", len(events) - before, "failed_details", failed_details)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
