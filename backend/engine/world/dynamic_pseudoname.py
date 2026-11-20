"""Deterministic syllable-based pseudo-name generator for procedural dynamic scenes."""

from __future__ import annotations

import hashlib
import re

_BASE36_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

_ROOT_ONSETS: tuple[str, ...] = (
    "AL",
    "AR",
    "ASH",
    "BEL",
    "BRAN",
    "CAL",
    "COR",
    "DAL",
    "DRA",
    "DUN",
    "EL",
    "FAL",
    "FEN",
    "GAR",
    "HAL",
    "HEL",
    "JOR",
    "KAEL",
    "KEL",
    "KETH",
    "LOR",
    "MAL",
    "MAR",
    "MOR",
    "NOR",
    "OR",
    "RAL",
    "SOL",
    "TAL",
    "THAR",
    "TOR",
    "VAL",
    "VAR",
    "VEL",
    "VOR",
    "ZAN",
)

_ROOT_CODAS: tuple[str, ...] = (
    "AN",
    "AR",
    "ATH",
    "DOR",
    "DRIS",
    "EN",
    "ER",
    "ETH",
    "GAR",
    "ION",
    "IR",
    "IS",
    "ITH",
    "KOR",
    "MAR",
    "MIR",
    "MON",
    "MOR",
    "NEN",
    "NOR",
    "ON",
    "OR",
    "OS",
    "OTH",
    "RAK",
    "RAN",
    "REN",
    "RIK",
    "RIN",
    "ROS",
    "THAL",
    "TOR",
    "VAN",
    "VANE",
    "VORN",
    "WYN",
)

_SECOND_TOKENS: tuple[str, ...] = (
    "ASH",
    "BANE",
    "BARK",
    "BRIM",
    "CAIRN",
    "CLEFT",
    "CRAG",
    "CREST",
    "DEEP",
    "DELVE",
    "DUSK",
    "FANG",
    "FELL",
    "FEN",
    "FOLD",
    "FORGE",
    "GALE",
    "GLADE",
    "GLOOM",
    "GRIM",
    "HOLD",
    "HOLLOW",
    "KETH",
    "MIRE",
    "MIST",
    "MOOR",
    "REACH",
    "RIFT",
    "RUIN",
    "SHADE",
    "SPIRE",
    "THORN",
    "VALE",
    "VAULT",
    "VEIL",
    "WARD",
)


def _normalize_seed_token(raw: object, fallback: str = "ZONE", max_len: int = 24) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(raw or "").strip().upper()).strip("_")
    return (cleaned or fallback)[:max_len]


def generate_deterministic_pseudoname(seed_text: str, max_len: int = 16) -> str:
    """Return a deterministic uppercase pronounceable pseudo-name matching ``^[A-Z0-9_]+$``."""
    safe_max = max(4, int(max_len))
    digest = hashlib.sha256(str(seed_text or "DYNAMIC").encode("utf-8")).digest()

    onset = _ROOT_ONSETS[digest[0] % len(_ROOT_ONSETS)]
    coda = _ROOT_CODAS[digest[1] % len(_ROOT_CODAS)]
    second = _SECOND_TOKENS[digest[2] % len(_SECOND_TOKENS)]
    tag_a = _BASE36_ALPHABET[digest[3] % len(_BASE36_ALPHABET)]
    tag_b = _BASE36_ALPHABET[digest[4] % len(_BASE36_ALPHABET)]

    first_word = f"{onset}{coda}"[:7]
    second_word = f"{second[:4]}{tag_a}{tag_b}"
    combined = f"{first_word}_{second_word}"
    if len(combined) <= safe_max:
        return combined
    trimmed = combined[:safe_max].rstrip("_")
    return trimmed or first_word[:safe_max]


def build_dynamic_placeholder_scene_id(
    zone_id: str,
    depth: int = 1,
    index: int = 1,
    suffix: str = "",
) -> str:
    """Build a deterministic ``DYN_*`` placeholder scene ID (max 20 chars) via pseudo-names."""
    norm_zone = _normalize_seed_token(zone_id, fallback="ZONE", max_len=24)
    safe_depth = max(1, int(depth or 1))
    safe_index = max(1, int(index or 1))
    norm_suffix = re.sub(r"[^A-Z0-9]+", "", str(suffix or "").upper())[:8]
    seed_text = f"{norm_zone}:D{safe_depth}:I{safe_index}:S{norm_suffix}"
    pseudo = generate_deterministic_pseudoname(seed_text, max_len=16)
    return f"DYN_{pseudo}"[:20].rstrip("_")
