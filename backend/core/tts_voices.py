"""Shared Google TTS voice catalog used across settings and world generation."""

from typing import TypedDict

from typing_extensions import NotRequired


class VoiceCatalogEntry(TypedDict):
    name: str
    gender: NotRequired[str | None]
    description: NotRequired[str | None]


GOOGLE_TTS_VOICE_CATALOG: list[VoiceCatalogEntry] = [
    {"name": "Zephyr", "gender": "female", "description": "Bright, Higher pitch"},
    {"name": "Puck", "gender": "male", "description": "Upbeat, Middle pitch"},
    {"name": "Charon", "gender": "male", "description": "Informative, Lower pitch"},
    {"name": "Kore", "gender": "female", "description": "Firm, Middle pitch"},
    {"name": "Fenrir", "gender": "female", "description": "Excitable, Lower middle pitch"},
    {"name": "Leda", "gender": "female", "description": "Youthful, Higher pitch"},
    {"name": "Orus", "gender": "male", "description": "Firm, Lower middle pitch"},
    {"name": "Aoede", "gender": "female", "description": "Breezy, Middle pitch"},
    {"name": "Callirrhoe", "gender": "female", "description": "Easy-going, Middle pitch"},
    {"name": "Autonoe", "gender": "female", "description": "Bright, Middle pitch"},
    {"name": "Enceladus", "gender": "male", "description": "Breathy, Lower pitch"},
    {"name": "Iapetus", "gender": "male", "description": "Clear, Lower middle pitch"},
    {"name": "Umbriel", "gender": "male", "description": "Easy-going, Lower middle pitch"},
    {"name": "Algieba", "gender": "male", "description": "Smooth, Lower pitch"},
    {"name": "Despina", "gender": "female", "description": "Smooth, Middle pitch"},
    {"name": "Erinome", "gender": "female", "description": "Clear, Middle pitch"},
    {"name": "Algenib", "gender": "male", "description": "Gravelly, Lower pitch"},
    {"name": "Rasalgethi", "gender": "male", "description": "Informative, Middle pitch"},
    {"name": "Laomedeia", "gender": "female", "description": "Upbeat, Higher Pitch"},
    {"name": "Achernar", "gender": "female", "description": "Soft, Higher pitch"},
    {"name": "Alnilam", "gender": "male", "description": "Firm, Lower middle pitch"},
    {"name": "Schedar", "gender": "male", "description": "Even, Lower middle pitch"},
    {"name": "Gacrux", "gender": "female", "description": "Mature, Middle pitch"},
    {"name": "Pulcherrima", "gender": "female", "description": "Forward, Middle pitch"},
    {"name": "Achird", "gender": "male", "description": "Friendly, Lower middle pitch"},
    {"name": "Zubenelgenubi", "gender": "male", "description": "Casual, Lower middle pitch"},
    {"name": "Vindemiatrix", "gender": "female", "description": "Gentle, Middle pitch"},
    {"name": "Sadachbia", "gender": "male", "description": "Lively, Lower pitch"},
    {"name": "Sadaltager", "gender": "male", "description": "Knowledgeable, Middle pitch"},
    {"name": "Sulafat", "gender": "female", "description": "Warm, Middle pitch"},
]

GOOGLE_TTS_VOICE_LIST: list[str] = [entry["name"] for entry in GOOGLE_TTS_VOICE_CATALOG]
GOOGLE_TTS_VOICE_NAMES: set[str] = set(GOOGLE_TTS_VOICE_LIST)
