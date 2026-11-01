from src.normalize_categories import DISPLAY_CATEGORIES, normalize


def main():
    events = [
        {"title": "パンマルシェ", "category": "グルメ", "source": "x", "venue": "x"},
        {"title": "コミックフロンティア", "category": "展示会・イベント", "source": "アクトシティ浜松", "venue": "x"},
        {"title": "オペラコンクール", "category": "展示会・イベント", "source": "アクトシティ浜松", "venue": "x"},
        {"title": "デジタルスタンプラリー", "category": "その他", "source": "x", "venue": "x"},
        {"title": "プライベートイベント", "category": "その他", "source": "x", "venue": "x"},
    ]
    normalize(events)

    assert events[0]["category"] == "グルメ・マーケット"
    assert events[1]["category"] == "ゲーム・アニメ"
    assert events[2]["category"] == "音楽・舞台"
    assert events[3]["category"] == "体験・ファミリー"
    assert events[4]["category"] == "その他"
    assert events[0]["source_category"] == "グルメ"
    assert all(e["category"] in DISPLAY_CATEGORIES for e in events)

    # Re-running must keep the original source category.
    normalize(events)
    assert events[0]["source_category"] == "グルメ"
    print("PASS")


if __name__ == "__main__":
    main()
