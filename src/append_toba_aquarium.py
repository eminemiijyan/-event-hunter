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

BASE = "https://aquarium.co.jp"
URL = BASE + "/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_RE = re.compile(
    r"(?P<sy>20\d{2})年\s*(?P<sm>\d{1,2})月\s*(?P<sd>\d{1,2})日.*?"
    r"[～〜~\-]\s*(?P<ey>20\d{2})年\s*(?P<em>\d{1,2})月\s*(?P<ed>\d{1,2})日"
)
PREFIX_RE = re.compile(
    r"^20\d{2}年\s*\d{1,2}月\s*\d{1,2}日（[^）]*）\s*[～〜~\-]\s*"
    r"20\d{2}年\s*\d{1,2}月\s*\d{1,2}日（[^）]*）\s*"
)
MAJOR_WORDS = ("企画展", "特別展", "正月", "クリスマス", "Xmas", "ハロウィ", "祭", "フェス", "周年", "コラボ")
EXCLUDE_WORDS = ("バックヤードツアー", "トレーナー体験", "天気予報水槽", "募集", "キャンペーン")


def fetch_html(url: str = URL, attempts: int = 3) -> str:
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
            print(f"TOBA_AQUARIUM retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _is_major(title: str) -> bool:
    if any(word in title for word in EXCLUDE_WORDS):
        return False
    return any(word in title for word in MAJOR_WORDS)


def parse_active_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    ended_heading = None
    for h in soup.find_all(["h2", "h3"]):
        if "終了したイベント" in " ".join(h.get_text(" ", strip=True).split()):
            ended_heading = h
            break
    anchors = ended_heading.find_all_previous("a", href=True) if ended_heading else soup.find_all("a", href=True)
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in reversed(anchors):
        href = a.get("href", "").strip()
        url = urljoin(BASE, href)
        path = urlparse(url).path
        if not path.startswith("/event/") or path == "/event/":
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        m = DATE_RE.search(text)
        if not m:
            continue
        title = PREFIX_RE.sub("", text).replace("開催中", "").strip()
        if not title or not _is_major(title):
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
            "venue": "鳥羽水族館",
            "prefecture": "三重県",
            "category": "展示会" if "展" in title else "祭り・季節",
            "source": "鳥羽水族館",
            "official_url": url,
            "decision": "display",
            "decision_reason": "鳥羽水族館公式イベント情報の企画展・季節大型企画",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


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

    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("TOBA_AQUARIUM skipped: official event page unavailable", type(exc).__name__)
        return

    parsed = parse_active_events(html)
    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        print("TOBA_AQUARIUM no current major seasonal event")
        return

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
    print("TOBA_AQUARIUM found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
