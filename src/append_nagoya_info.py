from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from src.append_aichi_now import append_pickups

BASE = "https://www.nagoya-info.jp"
LIST_URL = BASE + "/event/?tdate={day}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"

BIG_EVENT_WORDS = (
    "フェス", "FES", "祭", "まつり", "夜市", "MARKET", "マーケット", "マルシェ",
    "フェア", "博覧", "カーニバル", "イルミネーション", "ハロウィン", "花火",
    "パレード", "アニメーション", "CINEMA", "グルメ", "FOOD", "コーヒー", "珈琲",
)

JP_DATE_RE = re.compile(r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日")


def fetch_html(url: str) -> str:
    r = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.7)"},
    )
    r.raise_for_status()
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    return r.text


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").strip()


def _is_candidate(title: str) -> bool:
    t = _norm(title).casefold()
    return any(_norm(word).casefold() in t for word in BIG_EVENT_WORDS)


def discover_candidate_links(page_html: str) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    out = []
    for card in soup.select("div.event-slider-item"):
        title_node = card.select_one("h4.event-slider-name")
        link = card.select_one("a.tdn[href]")
        if not title_node or not link:
            continue
        title = title_node.get_text(" ", strip=True)
        if not _is_candidate(title):
            continue
        url = urljoin(BASE, link["href"])
        if "/event/detail/" in url and url not in out:
            out.append(url)
    return out


def discover_pages(page_html: str) -> int:
    soup = BeautifulSoup(page_html, "html.parser")
    pages = [1]
    for a in soup.find_all("a", href=True):
        m = re.search(r"(?:\?|&)page=(\d+)", a["href"])
        if m:
            pages.append(int(m.group(1)))
    return min(max(pages), 10)


def _field_value(soup: BeautifulSoup, label: str) -> str | None:
    node = soup.find(string=lambda s: s and _norm(s) == label)
    if node:
        tag = node.parent
        sibling = tag.find_next_sibling(["td", "dd"]) if tag else None
        if sibling:
            return sibling.get_text(" ", strip=True)
    text = _norm(" ".join(soup.stripped_strings))
    if label == "日程":
        m = re.search(r"日程\s*(.*?)\s*(?:休館日|時間|開催場所)", text)
    else:
        m = re.search(r"開催場所\s*(.*?)\s*(?:料金|お問い合わせ先|ホームページURL|アクセス)", text)
    return m.group(1).strip() if m else None


def parse_dates(text: str) -> tuple[str, str] | None:
    text = _norm(text)
    matches = list(JP_DATE_RE.finditer(text))
    if not matches:
        return None
    year = None
    prev_month = None
    dates = []
    for m in matches:
        month = int(m.group("month"))
        if m.group("year"):
            year = int(m.group("year"))
        elif year is not None and prev_month is not None and month < prev_month:
            year += 1
        if year is None:
            continue
        day = int(m.group("day"))
        dates.append(f"{year:04d}-{month:02d}-{day:02d}")
        prev_month = month
    if not dates:
        return None
    return dates[0], dates[-1]


def category_for(title: str) -> str:
    t = _norm(title).casefold()
    if any(w.casefold() in t for w in ("夜市", "グルメ", "food", "コーヒー", "珈琲", "market", "マーケット", "マルシェ")):
        return "グルメ"
    if any(w.casefold() in t for w in ("アニメ", "cinema", "映画", "仮面ライダー")):
        return "ゲーム・アニメ"
    if any(w.casefold() in t for w in ("祭", "まつり", "フェス", "festa", "fes", "カーニバル", "花火", "イルミネーション", "ハロウィン")):
        return "祭り・季節"
    return "その他"


def parse_detail(page_html: str, url: str) -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    title_node = soup.find("h1")
    if not title_node:
        title_node = soup.select_one("h4.event-slider-name")
    if not title_node:
        return None
    title = _norm(title_node.get_text(" ", strip=True))
    if not _is_candidate(title):
        return None

    date_text = _field_value(soup, "日程")
    venue = _field_value(soup, "開催場所")
    if not date_text or not venue:
        return None
    dates = parse_dates(date_text)
    if not dates:
        return None
    start, end = dates
    full_text = _norm(" ".join(soup.stripped_strings))
    decision = "exclude" if ("中止" in title or "開催中止" in full_text[:1800]) else "display"
    return {
        "title": title,
        "start_date": start,
        "end_date": end,
        "venue": _norm(venue),
        "prefecture": "愛知県",
        "category": category_for(title),
        "source": "名古屋コンシェルジュ",
        "official_url": url,
        "decision": decision,
        "decision_reason": "名古屋市街の大型イベント語に該当" if decision == "display" else "中止表記あり",
    }


def collect_candidates(today) -> list[dict]:
    first_url = LIST_URL.format(day=today.isoformat())
    first_html = fetch_html(first_url)
    max_page = discover_pages(first_html)
    links = []
    for page in range(1, max_page + 1):
        html = first_html if page == 1 else fetch_html(first_url + f"&page={page}")
        for url in discover_candidate_links(html):
            if url not in links:
                links.append(url)

    horizon = today + timedelta(days=183)
    events = []
    for url in links:
        event = parse_detail(fetch_html(url), url)
        if not event:
            continue
        start = datetime.strptime(event["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(event["end_date"], "%Y-%m-%d").date()
        if end >= today and start <= horizon:
            events.append(event)
    return events


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    candidates = collect_candidates(today)
    before = len(events)
    merged = append_pickups(events, candidates)
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
    print("NAGOYA_INFO", "candidates", len(candidates), "added", len(merged) - before)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
