"""Shared Google TTS voice catalog used across settings and world generation."""

GOOGLE_TTS_VOICE_CATALOG: list[dict[str, str]] = [
    {"name": "Zephyr", "gender": "female"},
    {"name": "Puck", "gender": "male"},
    {"name": "Charon", "gender": "male"},
    {"name": "Kore", "gender": "female"},
    {"name": "Fenrir", "gender": "male"},
    {"name": "Leda", "gender": "female"},
    {"name": "Orus", "gender": "male"},
    {"name": "Aoede", "gender": "female"},
    {"name": "Callirrhoe", "gender": "female"},
    {"name": "Autonoe", "gender": "female"},
    {"name": "Enceladus", "gender": "male"},
    {"name": "Iapetus", "gender": "male"},
    {"name": "Umbriel", "gender": "male"},
    {"name": "Algieba", "gender": "male"},
    {"name": "Despina", "gender": "female"},
    {"name": "Erinome", "gender": "female"},
    {"name": "Algenib", "gender": "male"},
    {"name": "Rasalgethi", "gender": "male"},
    {"name": "Laomedeia", "gender": "female"},
    {"name": "Achernar", "gender": "male"},
    {"name": "Alnilam", "gender": "male"},
    {"name": "Schedar", "gender": "male"},
    {"name": "Gacrux", "gender": "male"},
    {"name": "Pulcherrima", "gender": "female"},
    {"name": "Achird", "gender": "male"},
    {"name": "Zubenelgenubi", "gender": "male"},
    {"name": "Vindemiatrix", "gender": "female"},
    {"name": "Sadachbia", "gender": "female"},
    {"name": "Sadaltager", "gender": "female"},
    {"name": "Sulafat", "gender": "female"},
]

GOOGLE_TTS_VOICE_LIST: list[str] = [entry["name"] for entry in GOOGLE_TTS_VOICE_CATALOG]
GOOGLE_TTS_VOICE_NAMES: set[str] = set(GOOGLE_TTS_VOICE_LIST)
