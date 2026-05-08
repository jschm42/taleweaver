"""Shared Google TTS voice catalog used across settings and world generation."""

from typing import NotRequired, TypedDict


class VoiceCatalogEntry(TypedDict):
    name: str
    gender: NotRequired[str]
    description: NotRequired[str]


GOOGLE_TTS_VOICE_CATALOG: list[VoiceCatalogEntry] = [
    {"name": "Zephyr", "gender": "female", "description": "Bright"},
    {"name": "Puck", "gender": "male", "description": "Upbeat"},
    {"name": "Charon", "gender": "male", "description": "Informative"},
    {"name": "Kore", "gender": "female", "description": "Firm"},
    {"name": "Fenrir", "gender": "male", "description": "Slightly Excited"},
    {"name": "Leda", "gender": "female", "description": "Youthful"},
    {"name": "Orus", "gender": "male", "description": "Corporate"},
    {"name": "Aoede", "gender": "female", "description": "Breezy"},
    {"name": "Callirrhoe", "gender": "female", "description": "Calm"},
    {"name": "Autonoe", "gender": "female", "description": "Bright"},
    {"name": "Enceladus", "gender": "male", "description": "Breathy"},
    {"name": "Iapetus", "gender": "male", "description": "Clear"},
    {"name": "Umbriel", "gender": "male", "description": "Calm"},
    {"name": "Algieba", "gender": "male", "description": "Smooth"},
    {"name": "Despina", "gender": "female", "description": "Smooth"},
    {"name": "Erinome", "gender": "female", "description": "Cloudless"},
    {"name": "Algenib", "gender": "male", "description": "Gritty"},
    {"name": "Rasalgethi", "gender": "male", "description": "Informative"},
    {"name": "Laomedeia", "gender": "female", "description": "Upbeat"},
    {"name": "Achernar", "gender": "male", "description": "Soft"},
    {"name": "Alnilam", "gender": "male", "description": "Firm"},
    {"name": "Schedar", "gender": "male", "description": "Straightforward"},
    {"name": "Gacrux", "gender": "male", "description": "Mature"},
    {"name": "Pulcherrima", "gender": "female", "description": "Forward"},
    {"name": "Achird", "gender": "male", "description": "Friendly"},
    {"name": "Zubenelgenubi", "gender": "male", "description": "Casual"},
    {"name": "Vindemiatrix", "gender": "female", "description": "Gentle"},
    {"name": "Sadachbia", "gender": "female", "description": "Lively"},
    {"name": "Sadaltager", "gender": "female", "description": "Knowledgeable"},
    {"name": "Sulafat", "gender": "female", "description": "Warm"},
]

GOOGLE_TTS_VOICE_LIST: list[str] = [entry["name"] for entry in GOOGLE_TTS_VOICE_CATALOG]
GOOGLE_TTS_VOICE_NAMES: set[str] = set(GOOGLE_TTS_VOICE_LIST)
