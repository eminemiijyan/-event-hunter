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

from src.append_aichi_now import append_pickups

PRIMARY_URL = "https://www.bunka.pref.mie.lg.jp/art-museum/54798037874.htm"
FALLBACK_URLS = (
    "https://www.pref.mie.lg.jp/app/events/search/0/1",
    "https://www.pref.mie.lg.jp/app/events/search/0/2",
)
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

FULL_DATE_RE = re.compile(r"(?P<y>20\d{2})年\s*(?P<m>\d{1,2})月\s*(?P<d>\d{1,2})日?")
END_DATE_RE = re.compile(r"[－ー―～〜~\-]\s*(?:(?P<y>20\d{2})年\s*)?(?P<m>\d{1,2})月\s*(?P<d>\d{1,2})日?")
SLASH_RANGE_RE = re.compile(r"(?P<sy>20\d{2})/(?P<sm>\d{1,2})/(?P<sd>\d{1,2})\s*[-－～〜]\s*(?P<ey>20\d{2})/(?P<em>\d{1,2})/(?P<ed>\d{1,2})")


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
            print(f"MIE_ART retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _record(title: str, start: date, end: date, official_url: str) -> dict:
    return {
        "title": " ".join(title.split()),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "venue": "三重県立美術館",
        "prefecture": "三重県",
        "category": "展示会",
        "source": "三重県立美術館",
        "official_url": official_url,
        "decision": "display",
        "decision_reason": "三重県立美術館公式の企画展（常設展・県民ギャラリー・関連講座を除外）",
    }


def parse_japanese_range(text: str) -> tuple[date, date] | None:
    text = " ".join(unicodedata.normalize("NFKC", text).split())
    m = FULL_DATE_RE.search(text)
    if not m:
        return None
    sy, sm, sd = int(m.group("y")), int(m.group("m")), int(m.group("d"))
    try:
        start = date(sy, sm, sd)
    except ValueError:
        return None

    end = start
    em = END_DATE_RE.search(text[m.end():])
    if em:
        ey = int(em.group("y")) if em.group("y") else sy
        month = int(em.group("m"))
        day = int(em.group("d"))
        if not em.group("y") and month < sm:
            ey += 1
        try:
            end = date(ey, month, day)
        except ValueError:
            end = start
    return start, end


def parse_primary(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    section = None
    for heading in soup.find_all(["h1", "h2"]):
        if "年度の企画展" in " ".join(heading.get_text(" ", strip=True).split()):
            section = heading
            break
    if section is None:
        return []

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for heading in section.find_all_next(["h2", "h3"]):
        if heading is section:
            continue
        if heading.name == "h2":
            break
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title:
            continue

        parts: list[str] = []
        node = heading.find_next_sibling()
        while node is not None and getattr(node, "name", None) not in ("h2", "h3"):
            if getattr(node, "get_text", None):
                parts.append(" ".join(node.get_text(" ", strip=True).split()))
            node = node.find_next_sibling()
        block = " ".join(p for p in parts if p)
        dates = parse_japanese_range(block)
        if not dates:
            continue
        start, end = dates
        key = (title, start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append(_record(title, start, end, PRIMARY_URL))

    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def parse_prefecture_listing(page_html: str, official_url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [" ".join(s.split()) for s in soup.stripped_strings]
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, line in enumerate(lines):
        m = SLASH_RANGE_RE.fullmatch(unicodedata.normalize("NFKC", line))
        if not m:
            continue
        title = ""
        for candidate in lines[i + 1:min(i + 5, len(lines))]:
            normalized_candidate = unicodedata.normalize("NFKC", candidate)
            if SLASH_RANGE_RE.fullmatch(normalized_candidate):
                break
            if "三重県立美術館" in candidate and "企画展" in candidate:
                title = candidate
                break
        if not title:
            continue

        title = re.sub(r"^[【〖]三重県立美術館[】〗]\s*", "", title).strip()
        title = re.sub(r"^企画展\s*[「『]?", "", title).strip()
        title = title.rstrip("」』").strip()
        try:
            start = date(int(m.group("sy")), int(m.group("sm")), int(m.group("sd")))
            end = date(int(m.group("ey")), int(m.group("em")), int(m.group("ed")))
        except ValueError:
            continue
        key = (title, start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append(_record(title, start, end, official_url))

    return sorted(out, key=lambda e: (e["start_date"], e["title"]))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    parsed: list[dict] = []
    primary_unavailable = False
    try:
        parsed = parse_primary(fetch_html(PRIMARY_URL))
    except requests.RequestException as exc:
        primary_unavailable = True
        print("MIE_ART primary unavailable", type(exc).__name__)

    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    fallback_reachable = False
    if not found:
        fallback_items: list[dict] = []
        for url in FALLBACK_URLS:
            try:
                html = fetch_html(url)
                fallback_reachable = True
                fallback_items.extend(parse_prefecture_listing(html, url))
            except requests.RequestException as exc:
                print("MIE_ART fallback unavailable", type(exc).__name__, url)
        found = [e for e in fallback_items if e["end_date"] >= today.isoformat()]
        if found:
            print("MIE_ART using official prefecture fallback")

    if not found:
        if primary_unavailable and not fallback_reachable:
            print("MIE_ART skipped: official sources unavailable")
        else:
            print("MIE_ART no future planning exhibitions on reachable official source")
        return

    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in merged),
        "hold": sum(e.get("decision") == "hold" for e in merged),
        "exclude": sum(e.get("decision") == "exclude" for e in merged),
    }
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print("MIE_ART parsed", len(parsed), "future", len(found), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
