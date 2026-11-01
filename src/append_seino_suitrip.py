"""West Gifu source runner.

The broad Suitrip page is intentionally not fetched here because it rejects/times out
from GitHub Actions. Run the official municipal alternatives instead.
"""

from src.append_anpachi_events import main as append_anpachi
from src.append_ibigawa_kanko import main as append_ibigawa
from src.append_ogaki_family import main as append_ogaki


def main() -> None:
    print("SEINO_OFFICIAL starting municipal alternatives")
    append_ogaki()
    append_ibigawa()
    append_anpachi()
    print("SEINO_OFFICIAL done")


if __name__ == "__main__":
    main()
