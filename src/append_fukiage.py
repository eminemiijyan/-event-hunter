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

BASE = "https://www.nipc.or.jp/fukiage"
HOME_URL = BASE + "/"
LIST_URL = BASE + "/event/?m={month}&y={year}"
SITE_DIR = Path(__file__).resolve().parents[1] / "site"
MONTHS_AHEAD = 6

ADMISSION_RE = re.compile(r"^(一般|招待)(無料|有料)(.+)$")
RANGE_RE = re.compile(
    r"^(?P<sm>\d{1,2})(?:月|/)(?P<sd>\d{1,2})日?\s*\([^)]*\)\s*[～〜~\-]\s*"
    r"(?:(?P<em>\d{1,2})(?:月|/))?(?P<ed>\d{1,2})日?\s*\([^)]*\)\s*(?P<title>.*)$"
)
SINGLE_RE = re.compile(
    r"^(?P<sm>\d{1,2})(?:月|/)(?P<sd>\d{1,2})日?\s*\([^)]*\)\s*(?P<title>.*)$"
)

TARGET_WORDS = (
    "フェス", "フェア", "festival", "expo", "エキスポ", "博", "祭", "まつり", "マルシェ",
    "コミック", "アニメ", "ゲーム", "トミカ", "リカちゃん", "ソフビ", "ホビー", "ミニッツ",
    "骨董", "クラフト", "紙博", "神絵", "技能プラザ", "ファミリー", "レプタイル", "展示会",
    "モーター", "キャンピング", "アウトドア", "スポーツ", "大会",
)
SMALL_OR_PRIVATE_WORDS = (
    "就職", "キャリアセミナー", "講習", "講座", "説明会", "相談会", "技能審査",
)


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
            print(f"FUKIAGE retry {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


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


def _clean(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _parse_dates_and_title(line: str, page_year: int, next_line: str = "") -> tuple[date, date, str] | None:
    line = _clean(line)
    m = RANGE_RE.match(line)
    if m:
        sm, sd = int(m.group("sm")), int(m.group("sd"))
        em = int(m.group("em") or sm)
        ed = int(m.group("ed"))
        ey = page_year + (1 if em < sm else 0)
        try:
            start = date(page_year, sm, sd)
            end = date(ey, em, ed)
        except ValueError:
            return None
        title = _clean(m.group("title") or next_line)
        return (start, end, title) if title else None

    m = SINGLE_RE.match(line)
    if not m:
        return None
    sm, sd = int(m.group("sm")), int(m.group("sd"))
    try:
        start = date(page_year, sm, sd)
    except ValueError:
        return None
    title = _clean(m.group("title") or next_line)
    return (start, start, title) if title else None


def _category(title: str, description: str) -> str:
    text = f"{title} {description}".casefold()
    if any(word in text for word in ("コミック", "アニメ", "ゲーム", "トミカ", "リカちゃん", "ソフビ", "神絵")):
        return "ゲーム"
    if any(word in text for word in ("スポーツ", "大会", "カップ", "パラ競技")):
        return "スポーツ"
    if any(word in text for word in ("祭", "まつり", "フェス", "フェスタ")):
        return "祭り・季節"
    return "展示会"


def _is_target(title: str, venue: str, description: str) -> bool:
    text = f"{title} {description}"
    if any(word in text for word in SMALL_OR_PRIVATE_WORDS):
        return False
    if "吹上ホール" in venue:
        return True
    folded = text.casefold()
    return any(word.casefold() in folded for word in TARGET_WORDS)


def parse_events(page_html: str, page_year: int, source_url: str) -> list[dict]:
    soup = BeautifulSoup(page_html, "html.parser")
    lines = [_clean(s) for s in soup.stripped_strings if _clean(s)]
    events: list[dict] = []

    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        parsed = _parse_dates_and_title(line, page_year, next_line)
        if not parsed:
            continue
        start, end, title = parsed

        access = ""
        venue = ""
        for candidate in reversed(lines[max(0, i - 4):i]):
            m = ADMISSION_RE.match(candidate.replace(" ", ""))
            if not m:
                continue
            access, _fee, venue = m.groups()
            break
        if access != "一般" or not venue:
            continue

        range_match = RANGE_RE.match(_clean(line))
        single_match = SINGLE_RE.match(_clean(line))
        title_in_line = bool(
            (range_match and range_match.group("title").strip())
            or (single_match and single_match.group("title").strip())
        )
        start_index = i + 1 if title_in_line else i + 2
        description_parts: list[str] = []
        for candidate in lines[start_index:min(start_index + 5, len(lines))]:
            if ADMISSION_RE.match(candidate.replace(" ", "")) or RANGE_RE.match(candidate) or SINGLE_RE.match(candidate):
                break
            if candidate.startswith(("主催", "問合", "お問い合わせ", "前売", "当日")):
                continue
            description_parts.append(candidate)
        description = " ".join(description_parts)

        if not _is_target(title, venue, description):
            continue

        events.append({
            "title": title,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "venue": f"名古屋市中小企業振興会館（{venue}）",
            "prefecture": "愛知県",
            "category": _category(title, description),
            "source": "吹上ホール",
            "official_url": source_url,
            "decision": "display",
            "decision_reason": "吹上ホール公式の一般向け大型・対象ジャンルイベント",
        })

    unique: dict[tuple[str, str, str], dict] = {}
    for event in events:
        unique[(event["title"], event["start_date"], event["venue"])] = event
    return sorted(unique.values(), key=lambda e: (e["start_date"], e["title"]))


def main() -> None:
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    events_path = SITE_DIR / "events.json"
    meta_path = SITE_DIR / "meta.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    found: list[dict] = []
    reachable = 0
    failed_months = 0
    used_homepage_fallback = False
    for year, month in month_pairs(today):
        url = LIST_URL.format(year=year, month=month)
        try:
            html = fetch_html(url)
        except requests.RequestException as exc:
            failed_months += 1
            print("FUKIAGE month unavailable", type(exc).__name__, year, month)
            continue
        reachable += 1
        parsed = parse_events(html, year, url)
        future = [e for e in parsed if e["end_date"] >= today.isoformat()]
        print("FUKIAGE", f"{year}-{month:02d}", "targets", len(future))
        found.extend(future)

    if not reachable:
        try:
            home_html = fetch_html(HOME_URL, attempts=1)
            found = [
                e for e in parse_events(home_html, today.year, HOME_URL)
                if e["end_date"] >= today.isoformat()
            ]
            used_homepage_fallback = bool(found)
            if used_homepage_fallback:
                print("FUKIAGE using official homepage fallback", "targets", len(found))
        except requests.RequestException as exc:
            print("FUKIAGE homepage unavailable", type(exc).__name__)

    if not found:
        if not reachable:
            print("FUKIAGE skipped: official monthly pages and homepage unavailable or unparseable")
            return
        raise RuntimeError("吹上ホール公式から今後の対象イベントを取得できませんでした。")

    before = len(events)
    merged = append_pickups(events, found)
    events_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {k: sum(e.get("decision") == k for e in merged) for k in ("display", "hold", "exclude")}
    degradation: list[str] = []
    if failed_months:
        degradation.append(f"月別ページ {failed_months}/{MONTHS_AHEAD}件取得失敗")
    if used_homepage_fallback:
        degradation.append("月別ページ全滅のため同一公式サイトのトップページを使用")
    if degradation:
        meta.setdefault("degraded_sources", {})["吹上ホール"] = " / ".join(degradation)
    meta.update({
        "updated_at": datetime.now(ZoneInfo("Asia/Tokyo")).isoformat(timespec="minutes"),
        "source_count": len({e.get("source") for e in merged if e.get("source")}),
        "event_count": len(merged),
        "decision_counts": counts,
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FUKIAGE found", len(found), "added", len(merged) - before, "failed_months", failed_months)
    print("DONE", len(merged), counts, "sources", meta["source_count"])


if __name__ == "__main__":
    main()
