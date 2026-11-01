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

BASE = "https://sekikanko.jp"
INDEX_URL = BASE + "/event/index.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MAX_LIST_PAGES = 5
MAX_DETAIL_LINKS = 80

DATE_RE = re.compile(r"(?:(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日")

MAJOR_WORDS = (
    "祭", "まつり", "フェス", "フェスタ", "マルシェ", "マーケット", "花火",
    "ライトアップ", "イルミネーション", "工場参観", "農業祭", "スタンプラリー",
    "大会", "実演", "一般公開", "ゴザール", "朝市", "フェア", "展",
)
MAJOR_CATEGORIES = (
    "飲食イベント・マルシェ", "体験イベント", "おまつり・伝統行事", "スポーツ",
    "自然・季節", "文化・芸術",
)
SMALL_WORDS = ("少人数", "教室", "講座", "講習会", "相談会", "勉強会")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                url,
                timeout=(10, 45),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                    "Accept-Language": "ja-JP,ja;q=0.9",
                },
            )
            r.raise_for_status()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"SEKI_KANKO retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def discover_listing_pages(index_html: str, root_url: str = INDEX_URL) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    pages = [root_url]
    for a in soup.select('a[href*="/event/index_"]'):
        href = a.get("href", "").strip()
        if not href:
            continue
        url = urljoin(BASE, href)
        if url not in pages:
            pages.append(url)
        if len(pages) >= MAX_LIST_PAGES:
            break
    return pages


def extract_detail_links(page_html: str) -> list[str]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[str] = []
    for a in soup.select('a[href*="/event/detail_"]'):
        href = a.get("href", "").strip()
        if not href:
            continue
        url = urljoin(BASE, href)
        if url not in out:
            out.append(url)
    return out


def parse_dates(text: str) -> tuple[str, str] | None:
    year: int | None = None
    month: int | None = None
    values: list[date] = []
    for m in DATE_RE.finditer(unicodedata.normalize("NFKC", text)):
        if m.group(1):
            year = int(m.group(1))
        if m.group(2):
            month = int(m.group(2))
        if year is None or month is None:
            continue
        try:
            values.append(date(year, month, int(m.group(3))))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def _label_value(soup: BeautifulSoup, label: str) -> str:
    for node in soup.find_all(["dt", "th", "span", "div", "p"]):
        text = " ".join(node.get_text(" ", strip=True).split())
        if text != label:
            continue
        if node.name == "dt" and node.find_next_sibling("dd"):
            return " ".join(node.find_next_sibling("dd").get_text(" ", strip=True).split())
        if node.name == "th" and node.find_next_sibling("td"):
            return " ".join(node.find_next_sibling("td").get_text(" ", strip=True).split())
        sibling = node.find_next_sibling()
        if sibling:
            return " ".join(sibling.get_text(" ", strip=True).split())
    text = " ".join(soup.stripped_strings)
    m = re.search(
        re.escape(label) + r"\s*(.*?)\s*(?:開催時間|開催場所|住所|電話番号|問い合わせ先|駐車場|ウェブサイト|料金|アクセス|備考)",
        text,
    )
    return m.group(1).strip() if m else ""


def _categories(soup: BeautifulSoup) -> str:
    text = " ".join(soup.stripped_strings)
    return " ".join(category for category in MAJOR_CATEGORIES if category in text)


def _is_major(title: str, categories: str) -> bool:
    if any(word in title for word in SMALL_WORDS):
        return False
    return any(word in title for word in MAJOR_WORDS) or any(category in categories for category in MAJOR_CATEGORIES)


def category_for(title: str, categories: str) -> str:
    text = f"{title} {categories}"
    if any(word in text for word in ("マルシェ", "マーケット", "飲食", "グルメ", "農業祭", "ゆず", "朝市")):
        return "グルメ"
    if any(word in text for word in ("祭", "まつり", "花火", "ライトアップ", "イルミネーション", "自然・季節")):
        return "祭り・季節"
    if any(word in text for word in ("スポーツ", "大会", "登山", "ラリー")):
        return "スポーツ"
    if any(word in text for word in ("展", "展示", "文化・芸術", "一般公開", "実演")):
        return "展示会"
    return "その他"


def parse_detail(page_html: str, url: str) -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    title = ""
    for node in soup.find_all(["h1", "h2"]):
        candidate = " ".join(node.get_text(" ", strip=True).split())
        if not candidate or candidate in ("イベント", "検索結果"):
            continue
        if "せき観光ナビ" in candidate:
            continue
        title = candidate
        break
    if not title:
        return None

    period = _label_value(soup, "開催期間")
    venue = _label_value(soup, "開催場所")
    if not period or not venue:
        return None
    dates = parse_dates(period)
    if not dates:
        return None

    categories = _categories(soup)
    if not _is_major(title, categories):
        return None

    start_date, end_date = dates
    page_text = " ".join(soup.stripped_strings)
    decision = "exclude" if ("中止" in title or "開催中止" in page_text[:1800]) else "display"
    return {
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "venue": venue,
        "prefecture": "岐阜県",
        "category": category_for(title, categories),
        "source": "せき観光ナビ",
        "official_url": url,
        "decision": decision,
        "decision_reason": "関市公式観光サイト掲載の主要イベント" if decision == "display" else "中止表記あり",
    }


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県" or existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def _collect_listing_pages() -> list[tuple[str, str]]:
    try:
        index_html = fetch_html(INDEX_URL)
    except requests.RequestException as exc:
        print("SEKI_KANKO skipped: official event list unavailable", type(exc).__name__)
        return []

    pages = [(INDEX_URL, index_html)]
    seen = {INDEX_URL}
    for page_url in discover_listing_pages(index_html):
        if page_url in seen or len(pages) >= MAX_LIST_PAGES:
            continue
        try:
            html = fetch_html(page_url, attempts=2)
        except requests.RequestException as exc:
            print("SEKI_KANKO list page skipped", type(exc).__name__, page_url)
            continue
        if not extract_detail_links(html):
            continue
        pages.append((page_url, html))
        seen.add(page_url)
    return pages


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    pages = _collect_listing_pages()
    if not pages:
        return

    detail_links: list[str] = []
    for _, html in pages:
        for url in extract_detail_links(html):
            if url not in detail_links:
                detail_links.append(url)
            if len(detail_links) >= MAX_DETAIL_LINKS:
                break
        if len(detail_links) >= MAX_DETAIL_LINKS:
            break

    found: list[dict] = []
    failed_details = 0
    for url in detail_links:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException as exc:
            failed_details += 1
            print("SEKI_KANKO detail skipped", type(exc).__name__, url)
            continue
        item = parse_detail(html, url)
        if item and item["end_date"] >= today.isoformat():
            found.append(item)

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = sorted(unique.values(), key=lambda e: (e["start_date"], e["title"]))

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

    print(
        "SEKI_KANKO pages", len(pages), "links", len(detail_links), "found", len(found),
        "added", len(events) - before, "failed_details", failed_details,
    )
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
