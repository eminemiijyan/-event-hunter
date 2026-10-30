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
            print(f"GIFU_CULTURE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("ライブ", "コンサート", "music", "masterpiece", "音楽", "ダンス", "バレエ")):
        return "コンサート・ショー"
    if any(w in t for w in ("祭", "まつり", "フェスタ", "フェス")):
        return "祭り・季節"
    if any(w in t for w in ("展示", "展覧", "作品展", "美術展")):
        return "展示会"
    if any(w in t for w in ("大会", "スポーツ", "ボディビル")):
        return "スポーツ"
    return "その他"


def decision_for(title: str) -> tuple[str, str]:
    if any(w in title for w in ("転職フェア", "就職", "進学", "説明会", "講習会", "キャリアガイダンス", "企業展")):
        return "hold", "一般向けだが、お出かけ候補としては用途が限定的なため保留"
    return "display", "岐阜市文化センター公式イベントカレンダー掲載の一般向け催事"


def _venue(first_cell: str) -> str:
    for name in ("催し広場", "小劇場", "展示室", "練習室", "音楽室", "舞台"):
        if name in first_cell:
            return f"岐阜市文化センター {name}"
    return "岐阜市文化センター"


def _month_for_table(table) -> tuple[int, int] | None:
    # 公式ページでは月見出しのHTMLタグが固定ではないため、直前の文字列を遡って探す。
    node = table.find_previous(string=lambda s: bool(s and MONTH_HEADING_RE.search(" ".join(str(s).split()))))
    if node is not None:
        m = MONTH_HEADING_RE.search(" ".join(str(node).split()))
        if m:
            return int(m.group(1)), int(m.group(2))

    # 念のため直前の要素群も走査する。
    prev = table
    for _ in range(30):
        prev = prev.find_previous()
        if prev is None:
            break
        if getattr(prev, "get_text", None):
            text = " ".join(prev.get_text(" ", strip=True).split())
            m = MONTH_HEADING_RE.search(text)
            if m:
                return int(m.group(1)), int(m.group(2))
    return None


def _dates_for_cell(first: str, year: int, month: int) -> tuple[date, date] | None:
    # 例: 28日・29日 / 28日～3月4日 の両方に対応。
    full = re.findall(r"(?:(\d{1,2})月)?(\d{1,2})日", first)
    if not full:
        return None
    values: list[date] = []
    cur_month = month
    cur_year = year
    for month_text, day_text in full:
        if month_text:
            new_month = int(month_text)
            if new_month < cur_month and cur_month == 12:
                cur_year += 1
            cur_month = new_month
        try:
            values.append(date(cur_year, cur_month, int(day_text)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values), max(values)


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
            if len(cells) < 2:
                continue
            first = " ".join(cells[0].get_text(" ", strip=True).split())
            title = " ".join(cells[1].get_text(" ", strip=True).split())
            if not title or "催し物名" in title:
                continue
            dates = _dates_for_cell(first, year, month)
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
                "venue": _venue(first),
                "prefecture": "岐阜県",
                "category": category_for(title),
                "source": "岐阜市文化センター",
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
