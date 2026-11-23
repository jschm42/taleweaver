#!/usr/bin/env python3
"""TaleWeaver Server API Client (for agents).

Drives a running TaleWeaver server over HTTP to validate blueprints, import
complete ``.adv`` manifests, run editor structural/AI validation, and generate
or upload visual assets (cover, protagonist, scenes, NPCs, objects).

Auth configuration (environment variables or CLI flags):
  TW_API_URL    Base server URL (default: http://localhost:8000)
  TW_USERNAME   Username for POST /api/auth/token
  TW_PASSWORD   Password for POST /api/auth/token
  TW_TOKEN      Optional pre-fetched Bearer token (skips /api/auth/token)

Usage:
  python scripts/adventure_api.py validate-blueprint <blueprint.txt> [--json]
  python scripts/adventure_api.py import <manifest.adv> [--validate] [--include-ai] [--generate-visuals]
  python scripts/adventure_api.py validate <template_id> [--include-ai] [--json]
  python scripts/adventure_api.py visuals <template_id> [--only-missing] [--targets cover,protagonist,scene,npc,object]
  python scripts/adventure_api.py upload-visual <template_id> <target_type> <target_id> <image_file>
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import httpx

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_API_URL = "http://localhost:8000"
ALL_VISUAL_TARGETS = ("cover", "protagonist", "scene", "npc", "object")
DEFAULT_TIMEOUT = 60.0
VISUAL_TIMEOUT = 240.0
_REPO_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_repo_dotenv() -> None:
    """Populate missing env vars from the repo `.env` file (shell env takes precedence)."""
    if not _REPO_ENV_FILE.is_file():
        return
    for raw_line in _REPO_ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


class ApiError(Exception):
    """Raised when an API call fails or returns an unexpected payload."""


def _error_detail(resp: httpx.Response) -> str:
    try:
        data = resp.json()
    except ValueError:
        return resp.text.strip() or f"HTTP {resp.status_code}"
    if isinstance(data, dict) and "detail" in data:
        return str(data["detail"])
    return json.dumps(data, ensure_ascii=False)


def _authenticate(
    client: httpx.Client, token: str | None, username: str | None, password: str | None
) -> None:
    if token:
        client.headers["Authorization"] = f"Bearer {token}"
        return
    if not username or not password:
        raise ApiError(
            "Authentication required: set TW_TOKEN or both TW_USERNAME and TW_PASSWORD "
            "(or pass --token / --username / --password)."
        )
    resp = client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
    )
    if resp.status_code != 200:
        raise ApiError(f"Login failed ({resp.status_code}): {_error_detail(resp)}")
    access_token = resp.json().get("access_token")
    if not access_token:
        raise ApiError("Login response did not include access_token.")
    client.headers["Authorization"] = f"Bearer {access_token}"


def _print_findings(label: str, findings: list[dict[str, Any]]) -> int:
    errors = 0
    for item in findings:
        sev = str(item.get("severity") or "warn").upper()
        if sev == "ERROR":
            errors += 1
        code = item.get("code", "unknown")
        loc = f" [{item['location']}]" if item.get("location") else ""
        print(f"  [{label}] {sev} {code}{loc}: {item.get('message', '')}")
    return errors


def _run_validate_blueprint(client: httpx.Client, args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    resp = client.post("/api/adventures/blueprint/validate", json={"text": text})
    if resp.status_code != 200:
        raise ApiError(f"Blueprint validation failed ({resp.status_code}): {_error_detail(resp)}")
    data = resp.json()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 1 if data.get("errors") else 0

    print(f"has_tags={data.get('has_tags')} counts={data.get('counts', {})}")
    for warn in data.get("warnings", []):
        print(f"  WARN line {warn.get('line', '?')}: {warn.get('message', warn)}")
    for err in data.get("errors", []):
        print(f"  ERROR line {err.get('line', '?')}: {err.get('message', err)}")
    return 1 if data.get("errors") else 0


def _run_validate_template(
    client: httpx.Client, template_id: str, include_ai: bool, as_json: bool
) -> int:
    resp = client.post(
        f"/api/adventures/{template_id}/editor/validate",
        json={"include_ai": include_ai},
        timeout=VISUAL_TIMEOUT if include_ai else DEFAULT_TIMEOUT,
    )
    if resp.status_code != 200:
        raise ApiError(f"Validation failed ({resp.status_code}): {_error_detail(resp)}")
    data = resp.json()
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        all_items = data.get("structural_findings", []) + data.get("ai_findings", [])
        return 1 if any(f.get("severity") == "error" for f in all_items) else 0

    structural = data.get("structural_findings", [])
    ai_findings = data.get("ai_findings", [])
    print(
        f"Validation for {template_id}: {len(structural)} structural, {len(ai_findings)} AI findings"
    )
    if data.get("ai_skipped_reason"):
        print(f"  AI skipped: {data['ai_skipped_reason']}")
    error_count = _print_findings("STRUCT", structural)
    error_count += _print_findings("AI", ai_findings)
    return 1 if error_count > 0 else 0


def _collect_visual_jobs(
    assets: dict[str, Any],
    template_id: str,
    allowed_types: set[str],
    only_missing: bool,
) -> list[tuple[str, str, str]]:
    """Return (target_type, target_id, label) tuples to regenerate."""
    jobs: list[tuple[str, str, str]] = []
    adv = assets.get("adventure") or {}
    if "cover" in allowed_types:
        has_cover = bool(adv.get("cover_image_url") or adv.get("image_url"))
        if not (only_missing and has_cover):
            jobs.append(("cover", template_id, adv.get("title") or "Cover"))

    protag = assets.get("protagonist") or {}
    if (
        "protagonist" in allowed_types
        and protag.get("id")
        and not (only_missing and protag.get("profile_image"))
    ):
        jobs.append(("protagonist", str(protag["id"]), protag.get("name") or "Protagonist"))

    if "scene" in allowed_types:
        for scene in assets.get("scenes") or []:
            if not scene.get("id") or (only_missing and scene.get("image_url")):
                continue
            jobs.append(("scene", str(scene["id"]), scene.get("label") or scene["id"]))

    if "npc" in allowed_types:
        for npc in assets.get("npcs") or []:
            if not npc.get("id") or (only_missing and npc.get("image_url")):
                continue
            jobs.append(("npc", str(npc["id"]), npc.get("name") or npc["id"]))

    if "object" in allowed_types:
        for obj in assets.get("objects") or []:
            if not obj.get("id") or str(obj.get("item_type") or "").upper() == "CONSTRUCTABLE":
                continue
            if only_missing and obj.get("image_url"):
                continue
            jobs.append(("object", str(obj["id"]), obj.get("name") or obj["id"]))
    return jobs


def _run_visuals(
    client: httpx.Client,
    template_id: str,
    allowed_types: set[str],
    only_missing: bool,
    use_advanced: bool,
    apply_style: bool,
    apply_appearance: bool,
) -> int:
    resp = client.get(f"/api/adventures/{template_id}/editor/assets")
    if resp.status_code != 200:
        raise ApiError(f"Failed to load editor assets ({resp.status_code}): {_error_detail(resp)}")

    jobs = _collect_visual_jobs(resp.json(), template_id, allowed_types, only_missing)
    if not jobs:
        print("No visual targets to generate.")
        return 0

    print(f"Generating {len(jobs)} visual(s) for {template_id}...")
    failures = 0
    for idx, (target_type, target_id, label) in enumerate(jobs, start=1):
        payload = {
            "target_type": target_type,
            "target_id": target_id,
            "use_advanced_model": use_advanced,
            "apply_style": apply_style,
            "apply_appearance": apply_appearance,
        }
        r = client.post(
            f"/api/adventures/{template_id}/visuals/regenerate",
            json=payload,
            timeout=VISUAL_TIMEOUT,
        )
        if r.status_code == 200:
            image_url = r.json().get("image_url", "")
            print(f"  [{idx}/{len(jobs)}] OK   {target_type}:{target_id} ({label}) -> {image_url}")
        else:
            failures += 1
            print(
                f"  [{idx}/{len(jobs)}] FAIL {target_type}:{target_id} ({label}) "
                f"({r.status_code}): {_error_detail(r)}"
            )
    return 1 if failures else 0


def _run_import(client: httpx.Client, args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.file).read_text(encoding="utf-8"))
    resp = client.post("/api/adventures/import", json=manifest)
    if resp.status_code != 201:
        raise ApiError(f"Import failed ({resp.status_code}): {_error_detail(resp)}")
    data = resp.json()
    template_id = data.get("adventure_id")
    if not template_id:
        raise ApiError(f"Import succeeded but no adventure_id returned: {data}")
    print(f"Imported adventure_id={template_id}")

    exit_code = 0
    if args.validate:
        exit_code = _run_validate_template(client, template_id, args.include_ai, as_json=False)
    if args.generate_visuals:
        vis_code = _run_visuals(
            client,
            template_id,
            set(ALL_VISUAL_TARGETS),
            only_missing=True,
            use_advanced=False,
            apply_style=True,
            apply_appearance=True,
        )
        exit_code = max(exit_code, vis_code)
    return exit_code


def _run_upload_visual(client: httpx.Client, args: argparse.Namespace) -> int:
    path = Path(args.image_file)
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "application/octet-stream"
    with path.open("rb") as fh:
        resp = client.post(
            f"/api/adventures/{args.template_id}/visuals/upload",
            data={"target_type": args.target_type, "target_id": args.target_id},
            files={"file": (path.name, fh, mime_type)},
            timeout=VISUAL_TIMEOUT,
        )
    if resp.status_code != 200:
        raise ApiError(f"Upload failed ({resp.status_code}): {_error_detail(resp)}")
    print(json.dumps(resp.json(), ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TaleWeaver Server API Client")
    parser.add_argument("--url", default=os.environ.get("TW_API_URL", DEFAULT_API_URL))
    parser.add_argument("--username", default=os.environ.get("TW_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("TW_PASSWORD"))
    parser.add_argument("--token", default=os.environ.get("TW_TOKEN"))

    sub = parser.add_subparsers(dest="command", required=True)

    p_bp = sub.add_parser("validate-blueprint", help="Validate a tagged Story Idea blueprint")
    p_bp.add_argument("file", help="Path to blueprint text/markdown file")
    p_bp.add_argument("--json", action="store_true", help="Emit raw JSON response")

    p_imp = sub.add_parser("import", help="Import an .adv JSON manifest")
    p_imp.add_argument("file", help="Path to .adv JSON manifest")
    p_imp.add_argument("--validate", action="store_true", help="Run editor validation after import")
    p_imp.add_argument("--include-ai", action="store_true", help="Include AI logic validation")
    p_imp.add_argument("--generate-visuals", action="store_true", help="Generate missing visuals")

    p_val = sub.add_parser("validate", help="Run editor validation on an existing template")
    p_val.add_argument("template_id", help="Adventure template ID")
    p_val.add_argument("--include-ai", action="store_true", help="Include AI logic validation")
    p_val.add_argument("--json", action="store_true", help="Emit raw JSON response")

    p_vis = sub.add_parser("visuals", help="Regenerate visual assets via server T2I")
    p_vis.add_argument("template_id", help="Adventure template ID")
    p_vis.add_argument("--only-missing", action="store_true", help="Skip targets with an image")
    p_vis.add_argument(
        "--targets",
        default=",".join(ALL_VISUAL_TARGETS),
        help="Comma-separated subset of cover,protagonist,scene,npc,object",
    )
    p_vis.add_argument("--use-advanced", action="store_true", help="Force advanced T2I model")
    p_vis.add_argument("--no-style", action="store_true", help="Disable selected style instruction")
    p_vis.add_argument("--no-appearance", action="store_true", help="Disable appearance keywords")

    p_up = sub.add_parser("upload-visual", help="Upload a local image for a visual target")
    p_up.add_argument("template_id", help="Adventure template ID")
    p_up.add_argument("target_type", choices=ALL_VISUAL_TARGETS)
    p_up.add_argument("target_id", help="Target ID (template_id for cover)")
    p_up.add_argument("image_file", help="Path to PNG/JPEG/WEBP image")
    return parser


def _dispatch(client: httpx.Client, args: argparse.Namespace) -> int:
    if args.command == "validate-blueprint":
        return _run_validate_blueprint(client, args)
    if args.command == "import":
        return _run_import(client, args)
    if args.command == "validate":
        return _run_validate_template(client, args.template_id, args.include_ai, args.json)
    if args.command == "visuals":
        allowed = {t.strip() for t in args.targets.split(",") if t.strip()}
        unknown = allowed - set(ALL_VISUAL_TARGETS)
        if unknown:
            raise ApiError(f"Unknown target types: {', '.join(sorted(unknown))}")
        return _run_visuals(
            client,
            args.template_id,
            allowed,
            args.only_missing,
            args.use_advanced,
            not args.no_style,
            not args.no_appearance,
        )
    if args.command == "upload-visual":
        return _run_upload_visual(client, args)
    return 0


def main() -> int:
    _load_repo_dotenv()
    args = _build_parser().parse_args()
    try:
        with httpx.Client(base_url=args.url.rstrip("/"), timeout=DEFAULT_TIMEOUT) as client:
            _authenticate(client, args.token, args.username, args.password)
            return _dispatch(client, args)
    except (ApiError, httpx.HTTPError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
