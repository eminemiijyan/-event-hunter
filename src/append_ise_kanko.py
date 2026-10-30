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

BASE = "https://ise-kanko.jp"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTHS_AHEAD = 6

LIST_DATE_RE = re.compile(
    r"(?P<sy>20\d{2})\.(?P<sm>\d{1,2})\.(?P<sd>\d{1,2}).*?"
    r"[〜～~\-]\s*(?P<ey>20\d{2})\.(?P<em>\d{1,2})\.(?P<ed>\d{1,2})"
)
PREFIX_RE = re.compile(
    r"^20\d{2}\.\d{1,2}\.\d{1,2}\([^)]*\)\s*[〜～~\-]\s*"
    r"20\d{2}\.\d{1,2}\.\d{1,2}\([^)]*\)\s*"
)
TARGET_WORDS = (
    "祭", "まつり", "楽市", "フェス", "フェスタ", "花火", "神楽", "初穂曳", "駅伝",
    "太鼓", "イルミ", "ライトアップ", "大会", "お木曳", "奉祝", "神事", "例大祭",
    "マルシェ", "クラフト", "グルメ", "嬉楽祭",
)
EXCLUDE_WORDS = (
    "講演", "会議", "セミナー", "相談", "ライドシェア", "交通規制", "募集", "説明会",
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
            print(f"ISE_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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
    return any(word in title for word in TARGET_WORDS)


def category_for(title: str) -> str:
    if any(w in title for w in ("花火", "祭", "まつり", "神楽", "初穂曳", "奉祝", "神事", "例大祭", "イルミ", "ライトアップ")):
        return "祭り・季節"
    if any(w in title for w in ("駅伝", "大会")):
        return "スポーツ"
    if any(w in title for w in ("楽市", "マルシェ", "グルメ")):
        return "グルメ"
    if any(w in title for w in ("クラフト", "展")):
        return "展示会"
    return "その他"


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        path = urlparse(urljoin(BASE, href)).path.rstrip("/") + "/"
        if not path.startswith("/event/") or path.startswith("/event/page/") or path == "/event/":
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        m = LIST_DATE_RE.search(unicodedata.normalize("NFKC", text))
        if not m:
            continue
        title = PREFIX_RE.sub("", text).strip()
        if not title or not _is_target(title):
            continue
        try:
            start = date(int(m.group("sy")), int(m.group("sm")), int(m.group("sd")))
            end = date(int(m.group("ey")), int(m.group("em")), int(m.group("ed")))
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
            "venue": "伊勢市",
            "prefecture": "三重県",
            "category": category_for(title),
            "source": "伊勢市観光協会",
            "official_url": urljoin(BASE, href),
            "decision": "display",
            "decision_reason": "伊勢市観光協会公式の月別イベント掲載から主要な祭・季節行事を抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def parse_detail_venue(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    for node in soup.find_all(["h2", "h3", "h4", "dt", "th"]):
        label = " ".join(node.get_text(" ", strip=True).split())
        if label != "場所":
            continue
        sibling = node.find_next_sibling()
        if sibling:
            value = " ".join(sibling.get_text(" ", strip=True).split())
            if value:
                return value
        if node.name == "dt" and node.find_next_sibling("dd"):
            value = " ".join(node.find_next_sibling("dd").get_text(" ", strip=True).split())
            if value:
                return value
        if node.name == "th" and node.find_next_sibling("td"):
            value = " ".join(node.find_next_sibling("td").get_text(" ", strip=True).split())
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
            print("ISE_KANKO month unavailable", type(exc).__name__, y, m)
            continue
        reachable += 1
        parsed = parse_listing(html)
        print("ISE_KANKO", f"{y}-{m:02d}", "targets", len(parsed))
        found.extend(e for e in parsed if e["end_date"] >= today.isoformat())

    if not reachable:
        print("ISE_KANKO skipped: official monthly pages unavailable")
        return

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = list(unique.values())

    for item in found:
        try:
            detail = fetch_html(item["official_url"], attempts=2)
            venue = parse_detail_venue(detail)
            if venue:
                item["venue"] = venue
        except requests.RequestException:
            pass

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
    print("ISE_KANKO found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
