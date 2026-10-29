from __future__ import annotations

import time
from datetime import date

import requests

from src.fetch_events import (
    IG_API_URL,
    KYODO_LIST_URL,
    SKY_LIST_URL,
    build_site,
    month_keys,
    month_keys_dash,
    parse_events,
    parse_ig_api,
    parse_kyodo_events,
)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EventHunterPersonal/0.9)"}


def _get(url: str, *, expect_json: bool = False, attempts: int = 3):
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(url, timeout=(8, 20), headers=HEADERS)
            r.raise_for_status()
            if expect_json:
                return r.json()
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding
            return r.text
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            print(f"RETRY {attempt}/{attempts}: {type(exc).__name__} {url}")
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    raise last_error


def _fetch_sky(today: date):
    out = []
    print("SOURCE Aichi Sky Expo")
    for ym in month_keys(today, 6):
        url = SKY_LIST_URL.format(ym=ym)
        print("FETCH", url)
        try:
            html = _get(url)
        except requests.RequestException as exc:
            print(f"SOURCE Aichi Sky Expo SKIPPED after retries: {type(exc).__name__}")
            break
        found = parse_events(html, url)
        print("  ->", len(found), "events")
        out.extend(found)
    return out


def _fetch_ig(today: date):
    out = []
    print("SOURCE IG Arena")
    for ym in month_keys_dash(today, 6):
        url = IG_API_URL.format(ym=ym)
        print("FETCH", url)
        try:
            payload = _get(url, expect_json=True)
        except requests.RequestException as exc:
            print(f"SOURCE IG Arena SKIPPED after retries: {type(exc).__name__}")
            break
        found = parse_ig_api(payload, ym)
        print("  ->", len(found), "events")
        out.extend(found)
    return out


def _fetch_kyodo(today: date):
    allowed_months = set(month_keys_dash(today, 6))
    print("SOURCE Kyodo Tokai")
    print("FETCH", KYODO_LIST_URL)
    try:
        html = _get(KYODO_LIST_URL)
    except requests.RequestException as exc:
        print(f"SOURCE Kyodo Tokai SKIPPED after retries: {type(exc).__name__}")
        return []
    found = [
        e
        for e in parse_kyodo_events(html, KYODO_LIST_URL)
        if e.start_date[:7] in allowed_months
    ]
    print("  ->", len(found), "events")
    return found


def main():
    today = date.today()
    collected = []
    collected.extend(_fetch_sky(today))
    collected.extend(_fetch_ig(today))
    collected.extend(_fetch_kyodo(today))

    today_iso = today.isoformat()
    collected = [e for e in collected if e.end_date >= today_iso]
    unique = {(e.title, e.start_date, e.end_date, e.venue): e for e in collected}
    events = list(unique.values())
    if not events:
        raise RuntimeError("全基幹情報源が取得不能、または0件でした。公開データを生成しません。")

    build_site(events)
    counts = {
        "display": sum(e.decision == "display" for e in events),
        "hold": sum(e.decision == "hold" for e in events),
        "exclude": sum(e.decision == "exclude" for e in events),
    }
    print("DONE", len(events), counts, "sources", len({e.source for e in events}))


if __name__ == "__main__":
    main()
