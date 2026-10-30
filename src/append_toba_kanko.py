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

BASE = "https://www.toba.gr.jp"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTHS_AHEAD = 6
DETAIL_PATH_RE = re.compile(r"^/events/\d+/?$")
YEAR_RE = re.compile(r"^(20\d{2})年$")
MD_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")
FULL_DATE_RE = re.compile(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日")
SHORT_END_RE = re.compile(r"[～〜~\-]\s*(?:(20\d{2})年\s*)?(?:(\d{1,2})月\s*)?(\d{1,2})日")

TARGET_WORDS = (
    "祭", "まつり", "フェス", "フェスタ", "花火", "クラフト", "マルシェ", "大会", "イルミ",
    "ライトアップ", "恐竜", "神事", "例大祭", "市", "フェア",
)
EXCLUDE_WORDS = ("供養祭", "講座", "教室", "説明会", "相談", "ウォーキング", "巡礼")


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
            print(f"TOBA_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
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


def _title_from_link(text: str) -> str:
    return re.split(r"\s+(?:エリア|開催日|時間|場所|問い合わせ)", text, maxsplit=1)[0].strip()


def _is_target(title: str) -> bool:
    if any(word in title for word in EXCLUDE_WORDS):
        return False
    return any(word in title for word in TARGET_WORDS)


def _date_from_link_text(text: str) -> tuple[str, str] | None:
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
    em = SHORT_END_RE.search(tail)
    if em:
        ey = int(em.group(1)) if em.group(1) else sy
        mm = int(em.group(2)) if em.group(2) else sm
        dd = int(em.group(3))
        if not em.group(1) and mm < sm:
            ey += 1
        try:
            end = date(ey, mm, dd)
        except ValueError:
            end = start
    return start.isoformat(), end.isoformat()


def _date_from_nearby_list(link) -> tuple[str, str] | None:
    year: int | None = None
    month: int | None = None
    day: int | None = None
    for raw in link.find_all_previous(string=True, limit=18):
        text = " ".join(str(raw).split())
        if not text:
            continue
        if month is None:
            md = MD_RE.fullmatch(text)
            if md:
                month, day = int(md.group(1)), int(md.group(2))
                continue
        if year is None:
            ym = YEAR_RE.fullmatch(text)
            if ym:
                year = int(ym.group(1))
        if year is not None and month is not None and day is not None:
            break
    if year is None or month is None or day is None:
        return None
    try:
        d = date(year, month, day).isoformat()
    except ValueError:
        return None
    return d, d


def _venue_from_link_text(text: str) -> str:
    m = re.search(r"場所\s*(.*?)(?:\s*問い合わせ|\s*電話番号|$)", text)
    return m.group(1).strip() if m and m.group(1).strip() else "鳥羽市"


def category_for(title: str) -> str:
    if any(w in title for w in ("花火", "祭", "まつり", "神事", "例大祭", "イルミ", "ライトアップ")):
        return "祭り・季節"
    if any(w in title for w in ("クラフト", "フェア")):
        return "展示会"
    if any(w in title for w in ("マルシェ", "市")):
        return "グルメ"
    if any(w in title for w in ("大会", "恐竜")):
        return "スポーツ"
    return "その他"


def parse_listing(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
        url = urljoin(BASE, href)
        if not DETAIL_PATH_RE.match(urlparse(url).path):
            continue
        text = " ".join(link.get_text(" ", strip=True).split())
        title = _title_from_link(text)
        if not title or not _is_target(title):
            continue
        dates = _date_from_link_text(text) or _date_from_nearby_list(link)
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
            "venue": _venue_from_link_text(text),
            "prefecture": "三重県",
            "category": category_for(title),
            "source": "鳥羽市観光協会",
            "official_url": url,
            "decision": "display",
            "decision_reason": "鳥羽市観光協会公式の月別イベント掲載から主要な祭・季節イベントを抽出",
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

    found: list[dict] = []
    reachable = 0
    for y, m in month_pairs(today):
        url = f"{BASE}/events/?evtm={m}&evty={y}"
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print("TOBA_KANKO month unavailable", type(exc).__name__, y, m)
            continue
        reachable += 1
        parsed = parse_listing(html)
        print("TOBA_KANKO", f"{y}-{m:02d}", "targets", len(parsed))
        found.extend(e for e in parsed if e["end_date"] >= today.isoformat())

    if not reachable:
        print("TOBA_KANKO skipped: official monthly pages unavailable")
        return

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
    print("TOBA_KANKO found", len(found), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
