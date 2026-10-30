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

URL = "https://www.center-mie.or.jp/bunka/event/lineup"
BASE = "https://www.center-mie.or.jp"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

FULL_DATE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
RANGE_END_RE = re.compile(
    r"[～〜~\-]\s*(?:(20\d{2})年\s*)?(?:(\d{1,2})月\s*)?(\d{1,2})日"
)

SMALL_FORMAT_WORDS = (
    "ワンコインコンサート",
    "クラシック音楽講座",
    "オンステージコンサート",
)


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
            print(f"MIE_CULTURE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\-‐‑–—・･:：/／()（）\[\]【】『』「」]+", "", text)


def parse_dates(text: str) -> tuple[str, str] | None:
    text = " ".join(unicodedata.normalize("NFKC", text).split())
    m = FULL_DATE_RE.search(text)
    if not m:
        return None
    sy, sm, sd = map(int, m.groups())
    try:
        start = date(sy, sm, sd)
    except ValueError:
        return None

    end = start
    tail = text[m.end():]
    rm = RANGE_END_RE.search(tail)
    if rm:
        ey = int(rm.group(1)) if rm.group(1) else sy
        em = int(rm.group(2)) if rm.group(2) else sm
        ed = int(rm.group(3))
        try:
            end = date(ey, em, ed)
        except ValueError:
            end = start
    return start.isoformat(), end.isoformat()


def _event_block(heading) -> str:
    node = heading
    for _ in range(10):
        node = node.parent
        if node is None:
            break
        text = " ".join(node.get_text(" ", strip=True).split())
        if "開催期間" in text and "開催場所" in text and len(text) <= 1800:
            return text
    return ""


def _venue(text: str) -> str | None:
    if "三重県文化会館" not in text:
        return None
    if "大ホール" in text:
        return "三重県文化会館 大ホール"
    if "中ホール" in text:
        return "三重県文化会館 中ホール"
    if "小ホール" in text:
        return "三重県文化会館 小ホール"
    return "三重県文化会館"


def category_for(title: str) -> str:
    t = unicodedata.normalize("NFKC", title).casefold()
    if any(w in t for w in ("演劇", "ダンス", "舞台", "劇団", "バレエ")):
        return "コンサート・ショー"
    if any(w in t for w in ("管弦楽", "コンサート", "リサイタル", "音楽", "クァルテット", "フランセ")):
        return "コンサート・ショー"
    return "コンサート・ショー"


def parse_events(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.select('a[href*="/event/detail/"]'):
        href = link.get("href", "").strip()
        if not href:
            continue
        heading = link.find_previous("h2")
        if heading is None:
            continue
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title or title in ("2026年開催のイベント", "2027年開催のイベント"):
            continue
        if any(word in title for word in SMALL_FORMAT_WORDS):
            continue

        block = _event_block(heading)
        if not block:
            continue
        venue = _venue(block)
        if venue is None:
            continue
        dates = parse_dates(block)
        if not dates:
            continue
        start_date, end_date = dates
        key = (_norm(title), start_date)
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "venue": venue,
            "prefecture": "三重県",
            "category": category_for(title),
            "source": "三重県文化会館",
            "official_url": urljoin(BASE, href),
            "decision": "display",
            "decision_reason": "三重県文化会館公式の主催イベントラインナップ掲載公演（小規模定例企画を除外）",
        })

    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def _overlaps(a: dict, b: dict) -> bool:
    return a.get("end_date", "") >= b.get("start_date", "") and b.get("end_date", "") >= a.get("start_date", "")


def append_events(events: list[dict], new_events: list[dict]) -> list[dict]:
    out = list(events)
    for item in new_events:
        duplicate = any(
            _norm(e.get("title", "")) == _norm(item["title"]) and _overlaps(e, item)
            for e in out
        )
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
        html = fetch_html()
    except requests.RequestException as exc:
        print("MIE_CULTURE skipped: source unavailable", type(exc).__name__)
        return

    parsed = parse_events(html)
    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("三重県文化会館の主催イベントラインナップから今後の対象公演を取得できませんでした。")

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

    print("MIE_CULTURE parsed", len(parsed), "future", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
