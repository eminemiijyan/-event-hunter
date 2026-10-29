from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://aichinow.pref.aichi.jp"
WEEKEND_URL = BASE + "/events/weekend/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
JP_DATE_RE = re.compile(r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日")


def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.6)"})
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def pickup_links(page_html: str) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    heading = soup.find(lambda t: t.name in ("h2", "h3") and "ピックアップイベント" in t.get_text(" ", strip=True))
    if not heading:
        return []
    ul = heading.find_next("ul")
    if not ul:
        return []
    out = []
    for a in ul.find_all("a", href=True):
        href = a.get("href", "")
        if "/events/detail/" in href:
            url = urljoin(BASE, href)
            if url not in out:
                out.append(url)
    return out


def parse_dates(text: str) -> tuple[str, str] | None:
    matches = list(JP_DATE_RE.finditer(text))
    if not matches:
        return None
    year = None
    dates = []
    for m in matches:
        if m.group("year"):
            year = int(m.group("year"))
        if year is None:
            continue
        dates.append(f"{year:04d}-{int(m.group('month')):02d}-{int(m.group('day')):02d}")
    if not dates:
        return None
    return dates[0], dates[-1]


def category_for(title: str) -> str:
    t = title.casefold()
    if any(w.casefold() in t for w in ("グルメ", "発酵", "ビール", "酒", "sake", "フード", "珈琲", "コーヒー")):
        return "グルメ"
    if any(w.casefold() in t for w in ("祭", "まつり", "フェスタ", "花火", "イルミネーション", "ライトアップ")):
        return "祭り・季節"
    return "その他"


def parse_detail(page_html: str, url: str) -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    title_node = soup.find("h2")
    if not title_node:
        return None
    title = title_node.get_text(" ", strip=True)
    text = " ".join(soup.stripped_strings)

    dm = re.search(r"開催日\s*(.*?)\s*開催時間", text)
    vm = re.search(r"開催場所\s*(.*?)\s*所在地", text)
    if not dm or not vm:
        return None
    dates = parse_dates(dm.group(1))
    venue = vm.group(1).strip()
    if not dates or not venue:
        return None
    start, end = dates
    decision = "exclude" if ("中止" in title or "開催中止" in text[:1000]) else "display"
    return {
        "title": title,
        "start_date": start,
        "end_date": end,
        "venue": venue,
        "prefecture": "愛知県",
        "category": category_for(title),
        "source": "Aichi Now",
        "official_url": url,
        "decision": decision,
        "decision_reason": "Aichi Nowのピックアップイベント" if decision == "display" else "中止表記あり",
    }


def norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).casefold()
    return re.sub(r"[\s\-‐‑–—・･:：/／()（）\[\]【】]+", "", s)


def overlaps(a: dict, b: dict) -> bool:
    return a["end_date"] >= b["start_date"] and b["end_date"] >= a["start_date"]


def append_pickups(events: list[dict], pickups: list[dict]) -> list[dict]:
    out = list(events)
    for p in pickups:
        duplicate = any(norm_title(e.get("title", "")) == norm_title(p["title"]) and overlaps(e, p) for e in out)
        if not duplicate:
            out.append(p)
    return sorted(out, key=lambda e: (e.get("start_date", ""), e.get("title", "")))


def main():
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    links = pickup_links(fetch_html(WEEKEND_URL))
    if not links:
        raise RuntimeError("Aichi Nowのピックアップイベントを取得できませんでした。")

    pickups = []
    for url in links:
        event = parse_detail(fetch_html(url), url)
        if event and event["end_date"] >= date.today().isoformat():
            pickups.append(event)

    before = len(events)
    events = append_pickups(events, pickups)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {
        "display": sum(e.get("decision") == "display" for e in events),
        "hold": sum(e.get("decision") == "hold" for e in events),
        "exclude": sum(e.get("decision") == "exclude" for e in events),
    }
    meta.update({
        "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in events if e.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AICHI_NOW", "links", len(links), "parsed", len(pickups), "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
