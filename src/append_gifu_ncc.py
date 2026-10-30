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

URL = "https://www.g-ncc.jp/visitors/events-2/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTH_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*催し物案内")
DAY_RE = re.compile(r"(?:(\d{1,2})\s*/\s*)?(\d{1,2})\s*[（(]")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(10, 45), headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
                "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"GIFU_NCC retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _month_for_table(table) -> tuple[int, int] | None:
    node = table
    for _ in range(40):
        node = node.find_previous()
        if node is None:
            return None
        if getattr(node, "get_text", None):
            text = " ".join(node.get_text(" ", strip=True).split())
            m = MONTH_RE.search(text)
            if m:
                return int(m.group(1)), int(m.group(2))
    return None


def _dates(text: str, year: int, heading_month: int) -> tuple[date, date] | None:
    matches = DAY_RE.findall(text)
    if not matches:
        return None
    values: list[date] = []
    current_month = heading_month
    current_year = year
    for month_text, day_text in matches:
        if month_text:
            new_month = int(month_text)
            if current_month == 12 and new_month == 1:
                current_year += 1
            current_month = new_month
        try:
            values.append(date(current_year, current_month, int(day_text)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values), max(values)


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("コンサート", "live", "ライブ", "バレエ", "劇団", "吹奏楽", "交響楽", "シンフォニック")):
        return "コンサート・ショー"
    if any(w in t for w in ("スポーツ", "体操", "大会")):
        return "スポーツ"
    if any(w in t for w in ("祭", "フェス")):
        return "祭り・季節"
    return "その他"


def decision_for(title: str) -> tuple[str, str]:
    if any(w in title for w in ("学会", "認定試験", "模試", "研修会", "講習会")):
        return "hold", "一般来場の可能性はあるが、通常のお出かけ候補として用途が限定的なため保留"
    return "display", "長良川国際会議場公式の一般来場可能な催事"


def parse_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for table in soup.find_all("table"):
        ym = _month_for_table(table)
        if not ym:
            continue
        year, month = ym
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 5:
                continue
            day_text = " ".join(cells[0].get_text(" ", strip=True).split())
            venue = " ".join(cells[1].get_text(" ", strip=True).split())
            title = " ".join(cells[2].get_text(" ", strip=True).split())
            fee = " ".join(cells[4].get_text(" ", strip=True).split())
            if not title or "催し物名" in title or "関係者" in fee:
                continue
            dates = _dates(day_text, year, month)
            if not dates:
                continue
            start, end = dates
            key = (title, start.isoformat())
            if key in seen:
                continue
            decision, reason = decision_for(title)
            out.append({
                "title": title,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "venue": f"長良川国際会議場 {venue}".strip(),
                "prefecture": "岐阜県",
                "category": category_for(title),
                "source": "長良川国際会議場",
                "official_url": URL,
                "decision": decision,
                "decision_reason": reason,
            })
            seen.add(key)
    return out


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[\s\-‐‑–—・･:：/／()（）\[\]【】]+", "", s)


def _overlaps(a: dict, b: dict) -> bool:
    return a.get("end_date", "") >= b.get("start_date", "") and b.get("end_date", "") >= a.get("start_date", "")


def append_events(events: list[dict], new_events: list[dict]) -> list[dict]:
    out = list(events)
    for item in new_events:
        if any(_norm(e.get("title", "")) == _norm(item["title"]) and _overlaps(e, item) for e in out):
            continue
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
        print("GIFU_NCC skipped: source unavailable", type(exc).__name__)
        return

    found = [e for e in parse_events(html) if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("長良川国際会議場から今後の一般向けイベントを取得できませんでした。")

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

    print("GIFU_NCC found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
