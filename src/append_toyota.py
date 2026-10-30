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

from src.append_aichi_now import append_pickups

BASE = "https://www.tourismtoyota.jp"
CALENDAR_URL = BASE + "/events/calendar/{year:04d}-{month:02d}-01/"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_TOKEN_RE = re.compile(
    r"(?:(?P<year>20\d{2})年)?(?:(?P<month>\d{1,2})月)?(?P<day>\d{1,2})日"
)

MAJOR_WORDS = (
    "産業フェスタ",
    "香嵐渓もみじまつり",
    "もみじまつり",
    "四季桜まつり",
    "イルミネーションストーリー",
    "kiraboshi fes",
    "おいでんまつり",
    "花火",
    "豊田マラソン",
    "しもやまラリー",
    "rally japan",
    "ラリージャパン",
    "グランパス",
    "ヴェルブリッツ",
    "フェス",
    "festival",
)
MAJOR_VENUES = (
    "豊田スタジアム",
    "スカイホール豊田",
)
SKIP_WORDS = (
    "事前申込",
    "ツアー",
    "講座",
    "教室",
    "見学",
    "星見会",
    "フォトコンテスト",
    "スタンプラリー",
    "企画展",
    "美術館",
    "博物館",
    "ハイキング",
)


def month_keys(start: date, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


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
            print(f"TOYOTA retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _is_major(title: str, venue: str = "") -> bool:
    folded = _fold(title)
    if any(word.casefold() in folded for word in SKIP_WORDS):
        return False
    if any(word.casefold() in folded for word in MAJOR_WORDS):
        return True
    venue_folded = _fold(venue)
    return any(word.casefold() in venue_folded for word in MAJOR_VENUES)


def parse_dates(text: str, default_year: int | None = None) -> tuple[str, str] | None:
    text = unicodedata.normalize("NFKC", text)
    year = default_year
    month: int | None = None
    previous_month: int | None = None
    out: list[str] = []

    for match in DATE_TOKEN_RE.finditer(text):
        if match.group("year"):
            year = int(match.group("year"))

        explicit_month = match.group("month") is not None
        if explicit_month:
            new_month = int(match.group("month"))
            if (
                year is not None
                and previous_month is not None
                and new_month < previous_month
                and previous_month >= 9
                and new_month <= 3
            ):
                year += 1
            month = new_month
            previous_month = new_month

        if year is None or month is None:
            continue

        day = int(match.group("day"))
        try:
            out.append(date(year, month, day).isoformat())
        except ValueError:
            continue

    if not out:
        return None
    return out[0], out[-1]


def _dd_for_label(box, label: str):
    for dt in box.find_all("dt"):
        if dt.get_text(" ", strip=True).startswith(label):
            return dt.find_next_sibling("dd")
    return None


def _first_text(node) -> str:
    if node is None:
        return ""
    parts = list(node.stripped_strings)
    return parts[0].strip() if parts else ""


def category_for(title: str) -> str:
    folded = _fold(title)
    if any(word in folded for word in ("グランパス", "ヴェルブリッツ", "マラソン", "ラリー")):
        return "スポーツ"
    if "産業フェスタ" in folded:
        return "展示会"
    if any(word in folded for word in ("グルメ", "フード", "発酵", "酒", "ビール")):
        return "グルメ"
    if any(word in folded for word in (
        "まつり", "祭り", "もみじ", "四季桜", "イルミネーション", "花火", "フェス", "festival",
    )):
        return "祭り・季節"
    return "その他"


def parse_month(page_html: str, default_year: int) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    found: dict[str, dict] = {}

    for box in soup.select(".monthly_event_box"):
        link = box.select_one(".monthly_event_txt h2 a[href]")
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        url = urljoin(BASE, link.get("href", ""))

        date_dd = _dd_for_label(box, "開催日・期間")
        venue_dd = _dd_for_label(box, "開催場所")
        date_text = date_dd.get_text(" ", strip=True) if date_dd else ""
        venue = _first_text(venue_dd)
        area_node = box.select_one(".monthly_event_area .area")
        area = area_node.get_text(" ", strip=True) if area_node else ""

        if not _is_major(title, venue):
            continue

        dates = parse_dates(date_text, default_year=default_year)
        item = {
            "title": title,
            "official_url": url,
            "date_text": date_text,
            "venue": venue,
            "area": area,
            "start_date": dates[0] if dates else "",
            "end_date": dates[1] if dates else "",
        }

        old = found.get(url)
        if old is None or (not old.get("venue") and venue):
            found[url] = item

    return list(found.values())


def _detail_value(soup: BeautifulSoup, labels: set[str]) -> str:
    for tag in soup.find_all(["th", "dt"]):
        label = tag.get_text(" ", strip=True)
        if label not in labels:
            continue
        value = tag.find_next_sibling("td") if tag.name == "th" else tag.find_next_sibling("dd")
        if value:
            return value.get_text(" ", strip=True)
    return ""


def complete_from_detail(page_html: str, item: dict, default_year: int) -> dict:
    soup = BeautifulSoup(page_html, "html.parser")
    out = dict(item)

    if not out.get("start_date"):
        date_text = _detail_value(soup, {"開催時期", "開催期間", "開催日・期間"})
        dates = parse_dates(date_text, default_year=default_year)
        if dates:
            out["start_date"], out["end_date"] = dates

    if not out.get("venue"):
        venue_text = _detail_value(soup, {"開催場所"})
        if venue_text:
            out["venue"] = venue_text.split(" ")[0].strip()

    return out


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    candidates: dict[str, dict] = {}
    successful_months = 0
    total_boxes = 0

    for year, month in month_keys(today, 6):
        url = CALENDAR_URL.format(year=year, month=month)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"TOYOTA month skipped: {type(exc).__name__} {year:04d}-{month:02d}")
            continue

        successful_months += 1
        soup = BeautifulSoup(html, "html.parser")
        box_count = len(soup.select(".monthly_event_box"))
        total_boxes += box_count
        month_items = parse_month(html, default_year=year)
        print("TOYOTA", f"{year:04d}-{month:02d}", "boxes", box_count, "candidates", len(month_items))
        for item in month_items:
            candidates[item["official_url"]] = item

    if successful_months == 0:
        print("TOYOTA skipped: source unavailable after retries")
        return
    if total_boxes == 0:
        raise RuntimeError("ツーリズムとよたのイベント一覧を取得できませんでした。サイト構造変更の可能性があります。")

    found: list[dict] = []
    failed_details = 0
    for item in candidates.values():
        completed = dict(item)
        if not completed.get("start_date") or not completed.get("venue"):
            try:
                detail_html = fetch_html(completed["official_url"])
                completed = complete_from_detail(detail_html, completed, default_year=today.year)
            except requests.RequestException as exc:
                failed_details += 1
                print(f"TOYOTA detail skipped: {type(exc).__name__} {completed['official_url']}")

        if not completed.get("start_date"):
            continue
        if completed["end_date"] < today.isoformat():
            continue

        venue = completed.get("venue") or (
            f"豊田市・{completed.get('area')}エリア" if completed.get("area") else "豊田市"
        )
        found.append({
            "title": completed["title"],
            "start_date": completed["start_date"],
            "end_date": completed["end_date"],
            "venue": venue,
            "prefecture": "愛知県",
            "category": category_for(completed["title"]),
            "source": "ツーリズムとよた",
            "official_url": completed["official_url"],
            "decision": "display",
            "decision_reason": "豊田市公式観光サイト掲載の主要・家族向けイベント",
        })

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
    print("TOYOTA found", len(found), "added", len(merged) - before, "failed_details", failed_details)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
