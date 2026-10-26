#!/usr/bin/env python3
"""
Sync the ElevenLabs voice list (backend/core/elevenlabs_voices.json) with an ElevenLabs account.

Adds every voice of the account that is not in the list yet (with gender, age, accent and
description from ElevenLabs) and reports listed voices the account does not have. Hand-written
fields such as `good_for` are kept. Nothing is removed unless --prune is given.

Usage:
  poetry run python scripts/sync_elevenlabs_voices.py [--api-key KEY] [--output PATH] [--prune] [--dry-run]

The API key defaults to the ELEVENLABS_API_KEY environment variable / .env setting.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings  # noqa: E402
from backend.engine.elevenlabs_voices import BUNDLED_VOICE_LIST, looks_like_voice_id  # noqa: E402

VOICES_URL = "https://api.elevenlabs.io/v1/voices"


def fetch_account_voices(api_key: str) -> list[dict[str, Any]]:
    response = httpx.get(VOICES_URL, headers={"xi-api-key": api_key}, timeout=20.0)
    response.raise_for_status()
    return [
        v for v in response.json().get("voices") or [] if looks_like_voice_id(v.get("voice_id"))
    ]


def to_entry(voice: dict[str, Any]) -> dict[str, Any]:
    labels = voice.get("labels") if isinstance(voice.get("labels"), dict) else {}
    gender = str(labels.get("gender") or "").lower()
    description = labels.get("descriptive") or labels.get("description") or ""
    return {
        "id": voice["voice_id"],
        "name": voice.get("name") or voice["voice_id"],
        "gender": gender if gender in ("female", "male") else None,
        "age": str(labels.get("age") or "").replace("_", " "),
        "accent": str(labels.get("accent") or ""),
        "description": str(description).replace("_", " "),
        "good_for": [str(labels["use_case"]).replace("_", " ")] if labels.get("use_case") else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--output", type=Path, default=BUNDLED_VOICE_LIST)
    parser.add_argument(
        "--prune", action="store_true", help="remove listed voices the account lacks"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = args.api_key or settings.get_env_api_key("elevenlabs")
    if not api_key:
        print("No ElevenLabs API key: pass --api-key or set ELEVENLABS_API_KEY.", file=sys.stderr)
        return 1

    document = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {}
    listed: list[dict[str, Any]] = list(document.get("voices") or [])
    account = {v["voice_id"]: v for v in fetch_account_voices(api_key)}
    listed_ids = {entry.get("id") for entry in listed}

    added = [to_entry(voice) for voice_id, voice in account.items() if voice_id not in listed_ids]
    missing = [entry for entry in listed if entry.get("id") not in account]
    for entry in added:
        print(f"+ {entry['name']} ({entry['id']})")
    for entry in missing:
        print(
            f"{'-' if args.prune else '!'} {entry.get('name')} ({entry.get('id')}) is not in the account"
        )

    kept = [entry for entry in listed if not (args.prune and entry in missing)]
    document["voices"] = kept + added
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(document['voices'])} voices to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
