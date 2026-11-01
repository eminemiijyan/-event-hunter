from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1] / "site"

DISPLAY_CATEGORIES = (
    "グルメ・マーケット",
    "ゲーム・アニメ",
    "音楽・舞台",
    "展示・博覧会",
    "スポーツ",
    "祭り・季節",
    "セミナー・ビジネス",
    "体験・ファミリー",
    "その他",
)

DIRECT_MAP = {
    "グルメ": "グルメ・マーケット",
    "グルメ・マーケット": "グルメ・マーケット",
    "ゲーム": "ゲーム・アニメ",
    "ゲーム・アニメ": "ゲーム・アニメ",
    "コンサート・ショー": "音楽・舞台",
    "コンサート・舞台": "音楽・舞台",
    "展示会": "展示・博覧会",
    "スポーツ": "スポーツ",
    "祭り・季節": "祭り・季節",
    "セミナー・シンポジウム": "セミナー・ビジネス",
}


def _contains(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def display_category(event: dict) -> str:
    raw = str(event.get("source_category") or event.get("category") or "").strip()
    mapped = DIRECT_MAP.get(raw)
    if mapped:
        return mapped

    title = str(event.get("title") or "")
    source = str(event.get("source") or "")
    venue = str(event.get("venue") or "")
    text = f"{title} {source} {venue}".lower()

    if _contains(text, ("ファミリーセール", "プライベートイベント")):
        return "その他"
    if _contains(text, ("コミック", "アニメ", "ゲーム", "ポケモン", "カードゲーム", "デュエル", "プラモデル", "ロボフェス")):
        return "ゲーム・アニメ"
    if _contains(text, ("マルシェ", "マーケット", "market", "グルメ", "フード", "パン", "珈琲", "コーヒー", "楽市", "物産", "フルーツフェア", "さかな", "魚", "農園")):
        return "グルメ・マーケット"
    if _contains(text, ("セミナー", "シンポジウム", "フォーラム", "ビジネス", "技術会議", "マッチング", "キャリアガイダンス", "インターンシップ", "認定試験")):
        return "セミナー・ビジネス"
    if _contains(text, ("sports", "スポーツ")):
        return "スポーツ"
    if _contains(text, ("スタンプラリー", "体験", "あそび", "遊ぼう", "少年少女", "高校生トラベル", "マーブルタウン", "vr空間", "鑑賞サポート", "ミルキー☆サブウェイ")):
        return "体験・ファミリー"
    if _contains(text, ("コンサート", "ライブ", "live", "tour", "ツアー", "演奏", "バレエ", "ミュージカル", "公演", "舞台", "音楽", "オペラ", "吹奏楽", "ピアノ", "ヴァイオリ", "交響", "劇団", "お笑い", "第九", "ファンミーティング", "fan meeting")):
        return "音楽・舞台"
    if _contains(text, ("祭", "fes", "フェス", "大道芸", "紅葉", "コスモス", "菊花", "花火", "イルミ", "桜")):
        return "祭り・季節"
    if _contains(text, ("展示", "展覧", "博覧", "美術", "博物", "文化財", "考古学", "フェア", "expo", "公開")):
        return "展示・博覧会"

    if raw == "展示会・イベント" and source == "アクトシティ浜松":
        return "音楽・舞台"
    if raw in {"イベント", "その他", "展示会・イベント"} and source == "IGアリーナ":
        return "音楽・舞台"
    if raw == "展示会・イベント":
        return "展示・博覧会"
    return "その他"


def normalize(events: list[dict]) -> list[dict]:
    for event in events:
        if not event.get("source_category"):
            event["source_category"] = event.get("category") or "その他"
        event["category"] = display_category(event)
    return events


def main() -> None:
    events_path = SITE_DIR / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    normalize(events)
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(event.get("category") for event in events)
    print("CATEGORY_NORMALIZE", dict(counts))


if __name__ == "__main__":
    main()
