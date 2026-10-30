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

BASE = "https://okazaki-kanko.jp"
LIST_URL = BASE + "/event/list?category_x[]={category_id}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
DATE_TOKEN_RE = re.compile(
    r"(?:(?P<year>20\d{2})年(?:は)?)?(?:(?P<month>\d{1,2})月)?(?P<day>\d{1,2})日"
)

MAJOR_WORDS = (
    "秋まつり", "夏まつり", "桜まつり", "菊まつり", "あきまつり", "わんぱくまつり",
    "鬼祭り", "生誕祭", "ジャズストリート", "フェスタ", "フェス", "festival",
    "マーケット", "マルシェ", "花火", "家康行列", "消防出初", "イルミネーション",
    "ライトアップ", "green thread days", "ストーンフェスタ", "スタンプ大冒険",
    "初日の出",
)
SKIP_WORDS = (
    "中止", "募集", "教室", "講座", "トレッキング", "観察会", "ツアー", "定期演奏会",
    "講演会", "セミナー",
)


def month_keys(start: date, count: int = 6):
    y, m = start.year, start.month
    for _ in range(count):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def month_category_id(month: int) -> int:
    # 岡崎おでかけナビの月カテゴリ: 4月=22 ... 12月=30, 1月=31 ... 3月=33
    return month + 18 if month >= 4 else month + 30


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
            print(f"OKAZAKI retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _is_major(title: str) -> bool:
    folded = unicodedata.normalize("NFKC", title).casefold()
    if any(word.casefold() in folded for word in SKIP_WORDS):
        return False
    return any(word.casefold() in folded for word in MAJOR_WORDS)


def parse_dates(text: str) -> tuple[str, str] | None:
    text = unicodedata.normalize("NFKC", text)
    year: int | None = None
    month: int | None = None
    previous_day: int | None = None
    out: list[str] = []

    for match in DATE_TOKEN_RE.finditer(text):
        if match.group("year"):
            year = int(match.group("year"))
        explicit_month = match.group("month") is not None
        if explicit_month:
            month = int(match.group("month"))
        if year is None or month is None:
            continue

        day = int(match.group("day"))
        if not explicit_month and previous_day is not None and day < previous_day:
            month += 1
            if month == 13:
                month = 1
                year += 1
        try:
            out.append(date(year, month, day).isoformat())
        except ValueError:
            continue
        previous_day = day

    if not out:
        return None
    return out[0], out[-1]


def category_for(title: str) -> str:
    folded = unicodedata.normalize("NFKC", title).casefold()
    if "ジャズ" in folded or "ライブ" in folded:
        return "コンサート・ショー"
    if "マーケット" in folded or "マルシェ" in folded:
        return "グルメ"
    if any(word in folded for word in (
        "まつり", "祭り", "祭典", "フェスタ", "フェス", "festival", "花火",
        "イルミネーション", "ライトアップ", "初日の出", "生誕祭", "家康行列", "消防出初",
    )):
        return "祭り・季節"
    return "その他"


def parse_list(page_html: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    events: list[dict] = []
    for card in soup.select("article.spot"):
        link = card.select_one("h3 a[href]")
        if not link:
            continue
        title = link.get_text(" ", strip=True)
        if not _is_major(title):
            continue
        events.append({
            "title": title,
            "official_url": urljoin(BASE, link.get("href", "")),
        })

    unique = {event["official_url"]: event for event in events}
    return list(unique.values())


def parse_detail(page_html: str, title: str, url: str) -> dict | None:
    soup = BeautifulSoup(page_html, "html.parser")
    values: dict[str, str] = {}
    for th in soup.find_all("th"):
        label = th.get_text(" ", strip=True)
        if label not in {"開催期間", "開催場所"}:
            continue
        td = th.find_next_sibling("td")
        if td:
            values[label] = td.get_text(" ", strip=True)

    dates = parse_dates(values.get("開催期間", ""))
    venue = values.get("開催場所", "").strip()
    if not dates or not venue:
        return None

    start, end = dates
    return {
        "title": title,
        "start_date": start,
        "end_date": end,
        "venue": venue,
        "prefecture": "愛知県",
        "category": category_for(title),
        "source": "岡崎おでかけナビ",
        "official_url": url,
        "decision": "display",
        "decision_reason": "岡崎市観光協会公式掲載の主要・家族向けイベント",
    }


def main():
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    candidates: list[dict] = []
    successful_months = 0
    total_cards = 0
    for year, month in month_keys(today, 6):
        category_id = month_category_id(month)
        url = LIST_URL.format(category_id=category_id)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            print(f"OKAZAKI month skipped: {type(exc).__name__} {year:04d}-{month:02d}")
            continue
        successful_months += 1
        soup = BeautifulSoup(html, "html.parser")
        card_count = len(soup.select("article.spot"))
        total_cards += card_count
        month_candidates = parse_list(html)
        print("OKAZAKI", f"{year:04d}-{month:02d}", "cards", card_count, "candidates", len(month_candidates))
        candidates.extend(month_candidates)

    if successful_months == 0:
        print("OKAZAKI skipped: source unavailable after retries")
        return
    if total_cards == 0:
        raise RuntimeError("岡崎おでかけナビのイベント一覧を取得できませんでした。サイト構造変更の可能性があります。")

    candidates = list({item["official_url"]: item for item in candidates}.values())
    found: list[dict] = []
    failed_details = 0
    for item in candidates:
        try:
            detail_html = fetch_html(item["official_url"])
        except requests.RequestException as exc:
            failed_details += 1
            print(f"OKAZAKI detail skipped: {type(exc).__name__} {item['official_url']}")
            continue
        event = parse_detail(detail_html, item["title"], item["official_url"])
        if event and event["end_date"] >= today.isoformat():
            found.append(event)

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
    print("OKAZAKI found", len(found), "added", len(merged) - before, "failed_details", failed_details)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
