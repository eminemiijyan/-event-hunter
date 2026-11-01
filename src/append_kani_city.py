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

BASE = "https://www.city.kani.lg.jp"
INDEX_URL = BASE + "/dd.aspx?_PickUp_para=15&moduleid=30570"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
SOURCE = "可児市 イベント情報"
MAX_LIST_PAGES = 3
MAX_DETAIL_LINKS = 30

MAJOR_WORDS = (
    "フェスタ", "フェス", "まつり", "祭", "ライトアップ", "イルミ", "企画展", "特別展",
    "展示", "チャンバラ", "山城", "eスポ", "里山の日", "こども", "子ども", "マルシェ",
    "マーケット", "花火", "大会", "スポーツ", "大道芸", "公演", "音楽", "コンサート",
)
SMALL_WORDS = (
    "講座", "教室", "学級", "来庁", "追悼式", "図画・作文・標語", "楽習塾", "説明会", "相談会",
)
DATE_LABELS = ("開催期間", "開催日", "日時", "期日", "期間")
VENUE_LABELS = ("開催場所", "場所", "会場")
DATE_TOKEN_RE = re.compile(
    r"(?:(?:令和\s*(\d+)年)|(20\d{2})年)?\s*(?:(\d{1,2})月)?\s*(\d{1,2})日"
)


def fetch_html(url: str, attempts: int = 3) -> str:
    last_error: requests.RequestException | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(
                url,
                timeout=(10, 45),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/1.0)",
                    "Accept-Language": "ja-JP,ja;q=0.9",
                },
            )
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            print(f"KANI_CITY retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _norm(text: str) -> str:
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", _clean(text).casefold())


def _is_major_title(title: str) -> bool:
    if not title or any(word in title for word in SMALL_WORDS):
        return False
    return any(word.lower() in title.lower() for word in MAJOR_WORDS)


def discover_listing_pages(index_html: str, root_url: str = INDEX_URL) -> list[str]:
    soup = BeautifulSoup(index_html, "html.parser")
    pages = [root_url]
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if "moduleid=30570" not in href or "pfromid=" not in href:
            continue
        url = urljoin(BASE, href)
        if url not in pages:
            pages.append(url)
        if len(pages) >= MAX_LIST_PAGES:
            break
    return pages


def extract_detail_links(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "html.parser")
    out: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        title = _clean(a.get_text(" ", strip=True))
        href = a.get("href", "").strip()
        if not title or not href or not _is_major_title(title):
            continue
        if "山城に行こう" in title and "チャンバラ" not in title:
            # The combined Chambara page already contains the dated Yamashiro event.
            continue
        url = urljoin(BASE, href)
        if "city.kani.lg.jp" not in url:
            continue
        if not any(url.endswith(suffix) for suffix in (".htm", ".html")):
            continue
        pair = (title, url)
        if pair not in out:
            out.append(pair)
    return out


def parse_dates(text: str) -> tuple[str, str] | None:
    text = _clean(text)
    current_year: int | None = None
    current_month: int | None = None
    values: list[date] = []
    for match in DATE_TOKEN_RE.finditer(text):
        era_year, western_year, month, day = match.groups()
        if era_year:
            current_year = 2018 + int(era_year)
        elif western_year:
            current_year = int(western_year)
        if month:
            current_month = int(month)
        if current_year is None or current_month is None:
            continue
        try:
            values.append(date(current_year, current_month, int(day)))
        except ValueError:
            continue
    if not values:
        return None
    return min(values).isoformat(), max(values).isoformat()


def _section_value(soup: BeautifulSoup, labels: tuple[str, ...], max_chars: int = 320) -> str:
    for node in soup.find_all(["h2", "h3", "h4", "h5", "dt", "th", "p", "div", "li"]):
        text = _clean(node.get_text(" ", strip=True))
        if not text:
            continue
        matched_label = next(
            (label for label in labels if text == label or text.startswith(label + "：") or text.startswith(label + ":")),
            None,
        )
        if not matched_label:
            continue

        inline = _clean(re.sub(r"^" + re.escape(matched_label) + r"\s*[:：]?\s*", "", text, count=1))
        if inline:
            return inline[:max_chars]

        parts: list[str] = []
        for sibling in node.next_siblings:
            name = getattr(sibling, "name", None)
            if name in ("h2", "h3", "h4", "h5", "dt", "th"):
                break
            if hasattr(sibling, "get_text"):
                value = _clean(sibling.get_text(" ", strip=True))
            else:
                value = _clean(str(sibling))
            if value:
                parts.append(value)
            if len(" ".join(parts)) >= max_chars:
                break
        if parts:
            return " ".join(parts)[:max_chars]
    return ""


def category_for(title: str) -> str:
    lower = title.lower()
    if any(word in title for word in ("マルシェ", "マーケット", "グルメ", "キッチンカー")):
        return "グルメ"
    if any(word in title for word in ("企画展", "特別展", "展示", "展覧")):
        return "展示会"
    if any(word in lower for word in ("eスポ", "ゲーム", "アニメ")):
        return "ゲーム"
    if any(word in title for word in ("大道芸", "公演", "音楽", "コンサート")):
        return "コンサート・ショー"
    if any(word in title for word in ("祭", "まつり", "ライトアップ", "イルミ", "花火")):
        return "祭り・季節"
    if any(word in title for word in ("スポーツ", "大会", "マラソン")):
        return "スポーツ"
    return "イベント"


def _build_event(title: str, dates: tuple[str, str], venue: str, url: str) -> dict:
    return {
        "title": title,
        "start_date": dates[0],
        "end_date": dates[1],
        "venue": venue or "可児市内",
        "prefecture": "岐阜県",
        "category": category_for(title),
        "source": SOURCE,
        "official_url": url,
        "decision": "display",
        "decision_reason": "可児市公式イベント情報に掲載",
    }


def parse_subevents(page_html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    text = _clean(" ".join(soup.stripped_strings))
    pattern = re.compile(
        r"イベント名\s*[:：]\s*(.+?)\s+開催日\s*[:：]\s*(.+?)(?=\s+(?:時間|会場)\s*[:：])"
        r".*?会場\s*[:：]\s*(.+?)(?=\s+(?:定員|イベント名|チャンバラ|参加条件|※)|$)"
    )
    out: list[dict] = []
    for match in pattern.finditer(text):
        title = _clean(match.group(1))
        if not _is_major_title(title):
            continue
        dates = parse_dates(match.group(2))
        if not dates:
            continue
        venue = _clean(match.group(3))
        out.append(_build_event(title, dates, venue, url))
    return out


def parse_detail(page_html: str, url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    title = ""
    for node in soup.find_all(["h1", "h2"]):
        candidate = _clean(node.get_text(" ", strip=True))
        if not candidate or candidate in ("イベント情報", "可児市"):
            continue
        title = candidate
        break
    if not title or not _is_major_title(title):
        return []

    if "チャンバラ合戦" in title:
        subevents = parse_subevents(page_html, url)
        if subevents:
            return subevents

    date_text = _section_value(soup, DATE_LABELS)
    dates = parse_dates(date_text)
    if not dates:
        return []
    venue = _section_value(soup, VENUE_LABELS, max_chars=180)
    return [_build_event(title, dates, venue, url)]


def _same_event(existing: dict, candidate: dict) -> bool:
    if existing.get("prefecture") != "岐阜県":
        return False
    if existing.get("start_date") != candidate.get("start_date"):
        return False
    a = _norm(existing.get("title", ""))
    b = _norm(candidate.get("title", ""))
    return bool(a and b and (a == b or a in b or b in a))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    try:
        index_html = fetch_html(INDEX_URL)
    except requests.RequestException as exc:
        print("KANI_CITY skipped: official event list unavailable", type(exc).__name__)
        return

    pages = [(INDEX_URL, index_html)]
    for page_url in discover_listing_pages(index_html):
        if page_url == INDEX_URL or len(pages) >= MAX_LIST_PAGES:
            continue
        try:
            html = fetch_html(page_url, attempts=2)
        except requests.RequestException as exc:
            print("KANI_CITY list page skipped", type(exc).__name__, page_url)
            continue
        pages.append((page_url, html))

    details: list[tuple[str, str]] = []
    for _, html in pages:
        for pair in extract_detail_links(html):
            if pair not in details:
                details.append(pair)
            if len(details) >= MAX_DETAIL_LINKS:
                break
        if len(details) >= MAX_DETAIL_LINKS:
            break

    found: list[dict] = []
    failed_details = 0
    for _, url in details:
        try:
            html = fetch_html(url, attempts=2)
        except requests.RequestException as exc:
            failed_details += 1
            print("KANI_CITY detail skipped", type(exc).__name__, url)
            continue
        for item in parse_detail(html, url):
            if item["end_date"] >= today:
                found.append(item)

    unique: dict[tuple[str, str], dict] = {}
    for item in found:
        unique[(_norm(item["title"]), item["start_date"])] = item
    found = sorted(unique.values(), key=lambda event: (event["start_date"], event["title"]))

    before = len(events)
    for item in found:
        if not any(_same_event(existing, item) for existing in events):
            events.append(item)

    events.sort(key=lambda event: (event.get("start_date", ""), event.get("title", "")))
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {key: sum(event.get("decision") == key for event in events) for key in ("display", "hold", "exclude")}
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({event.get("source") for event in events if event.get("source")}),
        "event_count": len(events),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "KANI_CITY pages", len(pages), "links", len(details), "found", len(found),
        "added", len(events) - before, "failed_details", failed_details,
    )
    print("DONE", len(events), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
