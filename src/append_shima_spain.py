from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://www.parque-net.com"
LIST_URL = f"{BASE}/event/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_RE = re.compile(
    r"期間[:：]\s*(20\d{2})/(\d{1,2})/(\d{1,2})\s*[〜～~\-]\s*"
    r"(20\d{2})/(\d{1,2})/(\d{1,2})"
)
EXCLUDE_WORDS = ("謎解き", "VRアトラクション", "新VRアトラクション")


def fetch_html(url: str) -> str:
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


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def _category(title: str) -> str:
    if any(w in title for w in ("ハロウィーン", "クリスマス", "フェス", "festival", "さよなら")):
        return "祭り・季節"
    return "その他"


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for a in soup.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        normalized = unicodedata.normalize("NFKC", text)
        m = DATE_RE.search(normalized)
        if not m:
            continue
        title = normalized[: m.start()].strip()
        if not title or any(word in title for word in EXCLUDE_WORDS):
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
            "venue": "志摩スペイン村",
            "prefecture": "三重県",
            "category": _category(title),
            "source": "志摩スペイン村",
            "official_url": urljoin(BASE, a.get("href", "")),
            "decision": "display",
            "decision_reason": "志摩スペイン村公式イベント一覧から期間限定の季節・コラボ・特別イベントを抽出",
        })
    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def _horizon_start(today: date, months: int = 6) -> date:
    total = today.year * 12 + (today.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "三重県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a, b = _norm(existing.get("title", "")), _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    horizon = _horizon_start(today)
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        parsed = parse_listing(fetch_html(LIST_URL))
    except requests.RequestException as exc:
        print("SHIMA_SPAIN skipped", type(exc).__name__)
        return

    found = [
        e for e in parsed
        if e["end_date"] >= today.isoformat() and e["start_date"] < horizon.isoformat()
    ]
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
    print("SHIMA_SPAIN parsed", len(parsed), "future", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
