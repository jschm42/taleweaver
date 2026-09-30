import json
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "generation_sayings.json"


def _load_sayings() -> list[str]:
    if _DATA_PATH.is_file():
        try:
            with open(_DATA_PATH, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [str(s) for s in data]
        except Exception:
            pass
    return []


class GenerationSayings:
    SAYINGS: list[str] = _load_sayings()

