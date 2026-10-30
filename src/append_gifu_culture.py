from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

URL = "https://gifu-culture.info/events/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTH_HEADING_RE = re.compile(r"(20\d{2})年(\d{1,2})月イベント案内")
DAY_RE = re.compile(r"(\d{1,2})日")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 45), headers={
                "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            print(f"GIFU_CULTURE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("ライブ", "コンサート", "music", "masterpiece", "音楽", "ダンス")):
        return "コンサート・ショー"
    if any(w in t for w in ("祭", "まつり", "フェスタ", "フェス")):
        return "祭り・季節"
    if any(w in t for w in ("展示", "展覧", "作品展")):
        return "展示会"
    return "その他"


def decision_for(title: str) -> tuple[str, str]:
    if any(w in title for w in ("転職フェア", "説明会", "講習会")):
        return "hold", "一般向けだが、お出かけ候補としては用途が限定的なため保留"
    return "display", "岐阜市文化センター公式イベントカレンダー掲載の一般向け催事"


def _venue(first_cell: str) -> str:
    for name in ("催し広場", "小劇場", "展示室", "練習室", "音楽室", "舞台"):
        if name in first_cell:
            return f"岐阜市文化センター {name}"
    return "岐阜市文化センター"


def parse_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        m = MONTH_HEADING_RE.search(heading.get_text(" ", strip=True))
        if not m:
            continue
        year, month = map(int, m.groups())
        table = heading.find_next("table")
        if not table:
            continue
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            first = " ".join(cells[0].get_text(" ", strip=True).split())
            title = " ".join(cells[1].get_text(" ", strip=True).split())
            if not title or "催し物名" in title:
                continue
            days = [int(x) for x in DAY_RE.findall(first)]
            if not days:
                continue
            try:
                start = date(year, month, min(days))
                end = date(year, month, max(days))
            except ValueError:
                continue
            decision, reason = decision_for(title)
            out.append({
                "title": title,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "venue": _venue(first),
                "prefecture": "岐阜県",
                "category": category_for(title),
                "source": "岐阜市文化センター",
                "official_url": URL,
                "decision": decision,
                "decision_reason": reason,
            })
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[\s\-‐‑–—・･:：/／()（）\[\]【】]+", "", s)


def _overlaps(a: dict, b: dict) -> bool:
    return a.get("end_date", "") >= b.get("start_date", "") and b.get("end_date", "") >= a.get("start_date", "")


def append_events(events: list[dict], new_events: list[dict]) -> list[dict]:
    out = list(events)
    for item in new_events:
        duplicate = any(_norm(e.get("title", "")) == _norm(item["title"]) and _overlaps(e, item) for e in out)
        if not duplicate:
            out.append(item)
    return sorted(out, key=lambda e: (e.get("start_date", ""), e.get("title", "")))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html(URL)
    except requests.RequestException as exc:
        print("GIFU_CULTURE skipped: source unavailable", type(exc).__name__)
        return

    found = [e for e in parse_events(html) if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("岐阜市文化センターから今後のイベントを取得できませんでした。")

    before = len(events)
    events = append_events(events, found)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in events),
        "hold": sum(e.get("decision") == "hold" for e in events),
        "exclude": sum(e.get("decision") == "exclude" for e in events),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("GIFU_CULTURE found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
