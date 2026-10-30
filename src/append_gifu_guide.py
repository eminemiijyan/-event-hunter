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

BASE = "https://www.kankou-gifu.jp"
INDEX_URL = BASE + "/event/index.html"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MAX_LIST_PAGES = 4

DATE_RE = re.compile(r"(?:(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日")

MAJOR_WORDS = (
    "祭", "まつり", "フェス", "フェスタ", "花火", "マルシェ", "陶器", "クラフト",
    "グルメ", "フード", "全国", "大会", "ラリー", "アニメ", "ゲーム", "ライトアップ",
    "イルミネーション", "市", "フェア", "展", "イベント",
)
MAJOR_CATEGORIES = (
    "祭り・伝統行事", "グルメ", "スポーツ", "花火", "ライトアップ・イルミネーション",
    "朝市・マーケット",
)
SMALL_WORDS = ("教室", "講座", "少人数", "ワークショップのみ", "予約制ツアー")


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: Exception | None = None
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
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            print(f"GIFU_GUIDE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def discover_listing_pages(index_html: str) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    pages = [INDEX_URL]
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
    for m in DATE_RE.finditer(text):
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
    m = re.search(re.escape(label) + r"\s*(.*?)\s*(?:開催時間|開催場所|問い合わせ先|住所|電話番号|ウェブサイト|料金|アクセス)", text)
    return m.group(1).strip() if m else ""


def _is_major(title: str, categories: str) -> bool:
    if any(word in title for word in SMALL_WORDS):
        return False
    return any(word in title for word in MAJOR_WORDS) or any(cat in categories for cat in MAJOR_CATEGORIES)


def category_for(title: str, categories: str) -> str:
    text = f"{title} {categories}"
    if any(w in text for w in ("グルメ", "フード", "菓子", "栗", "朝市", "マーケット")):
        return "グルメ"
    if any(w in text for w in ("祭", "まつり", "花火", "ライトアップ", "イルミネーション")):
        return "祭り・季節"
    if any(w in text for w in ("スポーツ", "ラリー", "大会")):
        return "スポーツ"
    if any(w in text for w in ("アニメ", "ゲーム")):
        return "ゲーム"
    if any(w in text for w in ("展", "陶器", "クラフト")):
        return "展示会"
    return "その他"


def parse_detail(page_html: str, url: str) -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    title_node = soup.find(["h1", "h2"])
    if not title_node:
        return None
    title = " ".join(title_node.get_text(" ", strip=True).split())
    if not title:
        return None

    period = _label_value(soup, "開催期間")
    venue = _label_value(soup, "開催場所")
    if not period or not venue:
        return None
    dates = parse_dates(period)
    if not dates:
        return None

    page_text = " ".join(soup.stripped_strings)
    categories = " ".join(cat for cat in MAJOR_CATEGORIES if cat in page_text)
    if not _is_major(title, categories):
        return None

    start_date, end_date = dates
    decision = "exclude" if ("中止" in title or "開催中止" in page_text[:1500]) else "display"
    return {
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "venue": venue,
        "prefecture": "岐阜県",
        "category": category_for(title, categories),
        "source": "岐阜の旅ガイド",
        "official_url": url,
        "decision": decision,
        "decision_reason": "岐阜県観光公式サイト掲載の大型・お出かけ候補イベント" if decision == "display" else "中止表記あり",
    }


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県":
        return False
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        index_html = fetch_html(INDEX_URL)
    except requests.RequestException as exc:
        print("GIFU_GUIDE skipped: source unavailable", type(exc).__name__)
        return

    pages = discover_listing_pages(index_html)
    detail_links: list[str] = []
    for page_url in pages:
        try:
            html = index_html if page_url == INDEX_URL else fetch_html(page_url)
        except requests.RequestException as exc:
            print("GIFU_GUIDE list skipped", type(exc).__name__, page_url)
            continue
        for url in extract_detail_links(html):
            if url not in detail_links:
                detail_links.append(url)

    if not detail_links:
        raise RuntimeError("岐阜の旅ガイドのイベント詳細リンクを取得できませんでした。")

    found: list[dict] = []
    failed = 0
    for url in detail_links:
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            failed += 1
            print("GIFU_GUIDE detail skipped", type(exc).__name__, url)
            continue
        item = parse_detail(html, url)
        if item and item["end_date"] >= today.isoformat():
            found.append(item)

    if not found:
        raise RuntimeError("岐阜の旅ガイドから対象イベントを取得できませんでした。")

    before = len(events)
    for item in sorted(found, key=lambda e: (e["start_date"], e["title"])):
        if any(_same_event(existing, item) for existing in events):
            continue
        events.append(item)

    events = sorted(events, key=lambda e: (e.get("start_date", ""), e.get("title", "")))
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

    print("GIFU_GUIDE pages", len(pages), "links", len(detail_links), "found", len(found), "failed", failed, "added", len(events) - before)
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
