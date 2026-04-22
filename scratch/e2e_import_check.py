import asyncio
import io
import json
import sys
import zipfile
from pathlib import Path

import httpx
from sqlalchemy import select

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.auth import get_password_hash
from backend.core.database import AsyncSessionLocal
from backend.models.user import User

BASE = "http://127.0.0.1:8000/api"
USERNAME = "e2e_import_user"
PASSWORD = "e2e-import-pass"


def normalize_adv_payload(raw: dict, fallback_title: str) -> dict:
    if isinstance(raw, dict) and raw.get("version") and raw.get("title"):
        return raw

    adventure = raw.get("adventure", {}) if isinstance(raw, dict) else {}
    manifest = adventure.get("original_manifest") or raw.get("original_manifest") or {}
    protagonist = manifest.get("protagonist") or {}

    scenes = []
    for scene in manifest.get("scenes", []) or []:
        scenes.append(
            {
                "id": scene.get("id"),
                "title": scene.get("name") or scene.get("title"),
                "description": scene.get("description"),
                "is_hidden": bool(scene.get("is_hidden", False)),
            }
        )

    characters = []
    for npc in manifest.get("npcs", []) or []:
        characters.append(
            {
                "id": npc.get("id"),
                "name": npc.get("name"),
                "role": npc.get("npc_type") or npc.get("role"),
                "description": npc.get("description"),
                "start_scene_id": npc.get("start_scene_id") or npc.get("current_scene_id"),
                "is_npc": True,
            }
        )

    objects = []
    for obj in manifest.get("objects", []) or []:
        objects.append(
            {
                "id": obj.get("id"),
                "name": obj.get("name"),
                "type": obj.get("item_type") or obj.get("type"),
                "description": obj.get("description"),
                "start_scene_id": obj.get("start_scene_id") or obj.get("current_scene_id"),
            }
        )

    return {
        "version": str(raw.get("version") or "1.0"),
        "title": adventure.get("title") or raw.get("title") or fallback_title,
        "description": adventure.get("context") or raw.get("description"),
        "story_idea": adventure.get("context") or raw.get("story_idea"),
        "tone": adventure.get("selected_tone") or raw.get("tone"),
        "protagonist": {
            "name": protagonist.get("name"),
            "role": protagonist.get("role"),
            "description": protagonist.get("description"),
        },
        "scenes": scenes,
        "characters": characters,
        "objects": objects,
        "time_per_turn": adventure.get("time_per_turn") or raw.get("time_per_turn"),
        "pacing_minutes": adventure.get("pacing_minutes") or raw.get("pacing_minutes"),
        "clock_enabled": adventure.get("clock_enabled") if adventure.get("clock_enabled") is not None else raw.get("clock_enabled"),
        "generate_npc_images": bool(adventure.get("generate_npc_images", False)),
        "generate_item_images": bool(adventure.get("generate_item_images", False)),
        "automatic_cover_generation": False,
        "min_scenes": raw.get("min_scenes", 1),
        "max_scenes": raw.get("max_scenes", 5),
    }


async def ensure_user() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == USERNAME))
        user = result.scalars().first()
        if not user:
            user = User(username=USERNAME, hashed_password=get_password_hash(PASSWORD), role="admin")
            db.add(user)
        else:
            user.hashed_password = get_password_hash(PASSWORD)
            user.role = "admin"
        await db.commit()


def build_test_adz_bytes() -> bytes:
    manifest = {
        "adventure": {
            "title": "E2E ADZ Import Check",
            "context": "Generated during import flow verification.",
            "strict_rules": True,
            "rule_enforcement_mode": "rpg",
            "time_per_turn": 5,
            "pacing_minutes": 5,
            "clock_enabled": False,
            "heartbeat_enabled": False,
            "generate_scene_images": False,
            "generate_npc_images": False,
            "generate_item_images": False,
            "selected_image_styles": [],
            "selected_tone": "neutral",
        },
        "protagonist": {
            "name": "E2E Hero",
            "role": "Tester",
            "description": "Checks import pipeline",
        },
        "scenes": [
            {
                "id": "START",
                "name": "Start Room",
                "description": "A tiny room for API smoke tests.",
            }
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("adventure.adv", json.dumps(manifest, ensure_ascii=True))
    return buf.getvalue()


async def main() -> None:
    await ensure_user()

    adv_path = Path("test-adventures") / "kitchen_crisis.adv"
    raw_adv = json.loads(adv_path.read_text(encoding="utf-8"))
    adv_payload = normalize_adv_payload(raw_adv, fallback_title=adv_path.name)

    async with httpx.AsyncClient(timeout=60.0) as client:
        login = await client.post(
            f"{BASE}/auth/token",
            data={"username": USERNAME, "password": PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        before = await client.get(f"{BASE}/adventures", headers=headers)
        before.raise_for_status()
        before_count = len(before.json())

        adv_resp = await client.post(f"{BASE}/adventures/import", json=adv_payload, headers=headers)
        adv_ok = adv_resp.status_code in (200, 201)
        adv_body = adv_resp.json() if adv_resp.headers.get("content-type", "").startswith("application/json") else {"raw": adv_resp.text}
        adv_id = adv_body.get("adventure_id") if isinstance(adv_body, dict) else None

        adz_bytes = build_test_adz_bytes()
        files = {"file": ("e2e_import.adz", adz_bytes, "application/zip")}
        adz_resp = await client.post(f"{BASE}/adventures/import/adz", files=files, headers=headers)
        adz_ok = adz_resp.status_code in (200, 201)
        adz_body = adz_resp.json() if adz_resp.headers.get("content-type", "").startswith("application/json") else {"raw": adz_resp.text}
        adz_id = adz_body.get("adventure_id") if isinstance(adz_body, dict) else None

        after = await client.get(f"{BASE}/adventures", headers=headers)
        after.raise_for_status()
        adventures = after.json()
        after_count = len(adventures)
        ids = {a.get("adventure_id") for a in adventures}

    print("LOGIN: OK")
    print(f"ADV_IMPORT: status={adv_resp.status_code} ok={adv_ok} adventure_id={adv_id}")
    if not adv_ok:
        print(f"ADV_IMPORT_BODY: {adv_body}")
    print(f"ADZ_IMPORT: status={adz_resp.status_code} ok={adz_ok} adventure_id={adz_id}")
    if not adz_ok:
        print(f"ADZ_IMPORT_BODY: {adz_body}")
    print(f"ADVENTURES_COUNT: before={before_count} after={after_count} delta={after_count - before_count}")
    if adv_id:
        print(f"ADV_ID_PRESENT_IN_LIST: {adv_id in ids}")
    if adz_id:
        print(f"ADZ_ID_PRESENT_IN_LIST: {adz_id in ids}")


if __name__ == "__main__":
    asyncio.run(main())
