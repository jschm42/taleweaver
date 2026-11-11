#!/usr/bin/env python3
"""
Sync the ElevenLabs voice list (backend/core/elevenlabs_voices.json) with ElevenLabs.

Without --add: adds every voice of the account that is not in the list yet (with gender, age,
accent and description from ElevenLabs) and reports listed voices the account does not have.
Hand-written fields such as `good_for` are kept. Nothing is removed unless --prune is given.

With --add VOICE_ID [VOICE_ID ...]: looks up only these voices, in the account first and then
in the public Voice Library, and adds them to the list. A voice that is already listed gets
its ElevenLabs fields refreshed; its `good_for` hints are kept unless --good-for is given.

Usage:
  poetry run python scripts/sync_elevenlabs_voices.py [--api-key KEY] [--output PATH] [--prune] [--dry-run]
  poetry run python scripts/sync_elevenlabs_voices.py --add VOICE_ID [...] [--good-for "witch, elder"] [--dry-run]

The API key defaults to the ELEVENLABS_API_KEY environment variable / .env setting.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings  # noqa: E402
from backend.engine.audio.elevenlabs_voices import (  # noqa: E402
    BUNDLED_VOICE_LIST,
    looks_like_voice_id,
)

API_BASE = "https://api.elevenlabs.io/v1"
VOICES_URL = f"{API_BASE}/voices"
SHARED_VOICES_URL = f"{API_BASE}/shared-voices"
TIMEOUT = 20.0


def _as_client(client: httpx.Client | str) -> tuple[httpx.Client, bool]:
    if isinstance(client, httpx.Client):
        return client, False
    return httpx.Client(headers={"xi-api-key": client}, timeout=TIMEOUT), True


def fetch_account_voices(client: httpx.Client | str) -> list[dict[str, Any]]:
    http, close = _as_client(client)
    try:
        response = http.get(VOICES_URL)
        response.raise_for_status()
        return [
            v for v in response.json().get("voices") or [] if looks_like_voice_id(v.get("voice_id"))
        ]
    finally:
        if close:
            http.close()


def _labels_of_shared(voice: dict[str, Any]) -> dict[str, Any]:
    """Voice Library entries carry the labels as top-level fields."""
    keys = ("gender", "age", "accent", "descriptive", "use_case")
    return {key: voice.get(key) for key in keys if voice.get(key)}


def fetch_voice(client: httpx.Client | str, voice_id: str) -> tuple[dict[str, Any] | None, str]:
    """``(voice, source)`` for one id: the account first, then the public Voice Library."""
    http, close = _as_client(client)
    try:
        response = http.get(f"{VOICES_URL}/{voice_id}")
        if response.status_code == httpx.codes.OK:
            return response.json(), "account"
        if response.status_code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):
            response.raise_for_status()

        # Not in the account: the Voice Library search also matches voice ids; only an exact hit counts.
        response = http.get(
            SHARED_VOICES_URL,
            params={"search": voice_id, "page_size": 20},
        )
        response.raise_for_status()
        for voice in response.json().get("voices") or []:
            if voice.get("voice_id") == voice_id:
                return {**voice, "labels": _labels_of_shared(voice)}, "voice library"
        return None, ""
    finally:
        if close:
            http.close()


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


def parse_good_for(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [hint.strip() for hint in value.split(",") if hint.strip()]


def render(document: dict[str, Any]) -> str:
    """The list file as written by hand: other keys indented, one line per voice."""
    lines = ["{"]
    other = [(key, value) for key, value in document.items() if key != "voices"]
    for key, value in other:
        lines.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    voices = document.get("voices") or []
    lines.append('  "voices": [')
    for index, entry in enumerate(voices):
        inner = json.dumps(entry, ensure_ascii=False)[1:-1]
        comma = "," if index < len(voices) - 1 else ""
        lines.append(f"    {{ {inner} }}{comma}")
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def add_voices(
    client: httpx.Client | str,
    voice_ids: list[str],
    good_for: list[str] | None,
    listed: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """``(voices, ok)``: ``listed`` with the requested voices added or refreshed."""
    http, close = _as_client(client)
    try:
        voices = list(listed)
        ok = True
        for voice_id in voice_ids:
            if not looks_like_voice_id(voice_id):
                print(f"! {voice_id!r} is not an ElevenLabs voice id (20 letters/digits)")
                ok = False
                continue
            voice, source = fetch_voice(http, voice_id)
            if voice is None:
                print(f"! {voice_id} was found neither in your account nor in the Voice Library")
                ok = False
                continue
            entry = to_entry(voice)
            position = next((i for i, e in enumerate(voices) if e.get("id") == voice_id), None)
            if position is None:
                if good_for is not None:
                    entry["good_for"] = good_for
                voices.append(entry)
                print(f"+ {entry['name']} ({voice_id}) from the {source}: {_summary(entry)}")
                continue
            existing = voices[position]
            entry["good_for"] = good_for if good_for is not None else existing.get("good_for") or []
            voices[position] = {**existing, **entry}
            print(f"~ {entry['name']} ({voice_id}) refreshed from the {source}: {_summary(entry)}")
        return voices, ok
    finally:
        if close:
            http.close()


def _error_detail(response: httpx.Response) -> str:
    """ElevenLabs' own reason for a refused request, e.g. ``missing_permissions: ...``."""
    try:
        detail = response.json().get("detail")
    except ValueError:
        return ""
    if not isinstance(detail, dict):
        return str(detail or "")
    status, message = detail.get("status") or "", detail.get("message") or ""
    return f"{status}: {message}" if status and message else str(status or message)


def _key_source(args: argparse.Namespace) -> str:
    """Where the key came from; a shell variable silently overrides the value in .env."""
    if args.api_key:
        return "--api-key"
    if os.environ.get("ELEVENLABS_API_KEY"):
        return "the ELEVENLABS_API_KEY shell variable (overrides .env)"
    return ".env"


def _summary(entry: dict[str, Any]) -> str:
    """Console summary of a voice; the gender label stays in the list file only (not logged)."""
    traits = [entry.get("age"), entry.get("accent")]
    text = ", ".join(str(trait) for trait in traits if trait)
    if entry.get("description"):
        text += f"; {entry['description']}"
    if entry.get("good_for"):
        text += f"; good for: {', '.join(entry['good_for'])}"
    return text


def sync_account(
    client: httpx.Client | str, listed: list[dict[str, Any]], prune: bool
) -> list[dict[str, Any]]:
    http, close = _as_client(client)
    try:
        account = {v["voice_id"]: v for v in fetch_account_voices(http)}
        listed_ids = {entry.get("id") for entry in listed}

        added = [
            to_entry(voice) for voice_id, voice in account.items() if voice_id not in listed_ids
        ]
        missing = [entry for entry in listed if entry.get("id") not in account]
        for entry in added:
            print(f"+ {entry['name']} ({entry['id']})")
        for entry in missing:
            print(
                f"{'-' if prune else '!'} {entry.get('name')} ({entry.get('id')}) is not in the account"
            )
        kept = [entry for entry in listed if not (prune and entry in missing)]
        return kept + added
    finally:
        if close:
            http.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--output", type=Path, default=BUNDLED_VOICE_LIST)
    parser.add_argument(
        "--add", nargs="+", metavar="VOICE_ID", help="add or refresh only these voices"
    )
    parser.add_argument(
        "--good-for",
        default=None,
        help='comma-separated casting hints for --add, e.g. "witch, elder"',
    )
    parser.add_argument(
        "--prune", action="store_true", help="remove listed voices the account lacks"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.add and args.prune:
        parser.error("--prune cannot be combined with --add")
    if args.good_for is not None and not args.add:
        parser.error("--good-for only applies to --add")

    api_key = args.api_key or settings.get_env_api_key("elevenlabs")
    if not api_key:
        print("No ElevenLabs API key: pass --api-key or set ELEVENLABS_API_KEY.", file=sys.stderr)
        return 1

    document = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {}
    listed: list[dict[str, Any]] = list(document.get("voices") or [])
    ok = True
    try:
        with httpx.Client(headers={"xi-api-key": api_key}, timeout=TIMEOUT) as http_client:
            if args.add:
                voices, ok = add_voices(
                    http_client, args.add, parse_good_for(args.good_for), listed
                )
            else:
                voices = sync_account(http_client, listed, args.prune)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        print(f"ElevenLabs answered HTTP {status}", file=sys.stderr)
        detail = _error_detail(exc.response)
        if detail:
            print(f"  {detail}", file=sys.stderr)
        if status in (401, 403):
            print(f"  Key used from {_key_source(args)}.", file=sys.stderr)
            print(
                "  A restricted key needs the 'voices_read' permission (ElevenLabs > API Keys).",
                file=sys.stderr,
            )
        return 1
    except httpx.HTTPError as exc:
        print(f"ElevenLabs request failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1

    if voices == listed:
        print("Nothing to change.")
        return 0 if ok else 1
    document["voices"] = voices
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0 if ok else 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(document), encoding="utf-8")
    print(f"Wrote {len(voices)} voices to {args.output}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
