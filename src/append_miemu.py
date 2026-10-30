from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

URL = "https://www.bunka.pref.mie.lg.jp/MieMu/84764046737.htm"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

EXHIBIT_MARKER_RE = re.compile(r"^(?:特別展・)?第\d+回企画展$")
DATE_RANGE_RE = re.compile(
    r"(?P<sy>20\d{2})年\s*(?P<sm>\d{1,2})月\s*(?P<sd>\d{1,2})日"
    r".*?(?:から|～|〜|~)\s*"
    r"(?P<ey>20\d{2})年\s*(?P<em>\d{1,2})月\s*(?P<ed>\d{1,2})日"
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
            print(f"MIEMU retry {attempt}/{attempts}: {type(exc).__name__}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _parse_range(text: str) -> tuple[date, date] | None:
    m = DATE_RANGE_RE.search(" ".join(text.split()))
    if not m:
        return None
    try:
        return (
            date(int(m.group("sy")), int(m.group("sm")), int(m.group("sd"))),
            date(int(m.group("ey")), int(m.group("em")), int(m.group("ed"))),
        )
    except ValueError:
        return None


def parse_exhibitions(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [" ".join(s.split()) for s in soup.stripped_strings]
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for i, line in enumerate(lines):
        if not EXHIBIT_MARKER_RE.match(line):
            continue

        title = ""
        dates: tuple[date, date] | None = None
        for candidate in lines[i + 1:min(i + 8, len(lines))]:
            if not title:
                if candidate.startswith("期間") or EXHIBIT_MARKER_RE.match(candidate):
                    continue
                if candidate in ("企画展", "三重の実物図鑑 特集展示"):
                    continue
                title = candidate
                continue
            if "期間" in candidate or DATE_RANGE_RE.search(candidate):
                dates = _parse_range(candidate)
                if dates:
                    break

        if not title or not dates:
            continue
        start, end = dates
        key = (title, start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": "三重県総合博物館 MieMu",
            "prefecture": "三重県",
            "category": "展示会",
            "source": "三重県総合博物館 MieMu",
            "official_url": URL,
            "decision": "display",
            "decision_reason": "三重県総合博物館公式の企画展・特別展",
        })

    return out


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        html = fetch_html()
    except requests.RequestException as exc:
        print("MIEMU skipped: source unavailable", type(exc).__name__)
        return

    parsed = parse_exhibitions(html)
    found = [e for e in parsed if e["end_date"] >= today.isoformat()]
    if not found:
        raise RuntimeError("MieMu公式から今後の企画展・特別展を取得できませんでした。")

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

    print("MIEMU parsed", len(parsed), "future", len(found), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
