#!/usr/bin/env python3
"""Extract image assets from ADZ archives and generate a JSON index.

The script scans a source directory for `.adz` files, extracts image files from each
archive to a target directory, and writes a JSON file containing file names and a
short description. Descriptions are taken from `itemDescription` in the ADZ payload
when available, with fallback to common alternatives like `description`.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import ZipFile

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg"}
@dataclass
class ExtractedAsset:
    """Single extracted asset entry for the output JSON."""

    adventure: str
    filename: str
    name: str
    description: str
    typ: str
    image_style: str


class ADZAssetExtractor:
    """Extract entity image assets from ADZ archives and generate grouped metadata."""

    def __init__(self, source_dir: Path, target_dir: Path, output_json: Path) -> None:
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.output_json = output_json
        self.target_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> int:
        adz_files = sorted(self.source_dir.rglob("*.adz"))
        if not adz_files:
            print(f"Keine .adz-Dateien gefunden in: {self.source_dir}")
            return 1

        extracted_assets: list[ExtractedAsset] = []

        for adz_file in adz_files:
            print(f"Verarbeite: {adz_file}")
            assets = self._extract_from_archive(adz_file)
            extracted_assets.extend(assets)

        self._write_json(extracted_assets)
        print(f"\nExtraktion abgeschlossen: {len(extracted_assets)} Assets")
        print(f"JSON-Datei geschrieben: {self.output_json}")
        return 0

    def _extract_from_archive(self, adz_path: Path) -> list[ExtractedAsset]:
        records: list[ExtractedAsset] = []

        with ZipFile(adz_path, "r") as archive:
            adventure_entry = self._find_adventure_entry(archive)
            if adventure_entry is None:
                return records

            try:
                payload = json.loads(archive.read(adventure_entry).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return records

            blueprint = self._get_blueprint_root(payload)
            adventure_name = str(
                blueprint.get("title")
                or blueprint.get("name")
                or payload.get("title")
                or payload.get("name")
                or adz_path.stem
            )
            image_style = self._extract_image_style(payload, blueprint)
            adventure_dir = self.target_dir / self._sanitize_folder_name(adventure_name)
            adventure_dir.mkdir(parents=True, exist_ok=True)

            normalized_members = {
                self._normalize_path(name): name
                for name in archive.namelist()
            }

            for entity in self._collect_entities(payload, blueprint):
                archive_member = self._resolve_archive_member(entity["image_ref"], normalized_members)
                if archive_member is None:
                    continue

                extension = Path(archive_member).suffix.lower()
                if extension not in IMAGE_EXTENSIONS:
                    continue

                output_name = self._resolve_output_name(adventure_dir, f"{entity['id']}{extension}")
                output_path = adventure_dir / output_name
                output_path.write_bytes(archive.read(archive_member))

                records.append(
                    ExtractedAsset(
                        adventure=adventure_name,
                        filename=output_name,
                        name=entity["name"],
                        description=entity["description"],
                        typ=entity["typ"],
                        image_style=image_style,
                    )
                )

            self._write_adventure_json(adventure_dir, records)

        return records

    def _find_adventure_entry(self, archive: ZipFile) -> str | None:
        for name in archive.namelist():
            if name.lower().endswith(".adv"):
                return name
        return None

    def _get_blueprint_root(self, payload: dict[str, Any]) -> dict[str, Any]:
        adventure_node = payload.get("adventure")
        if isinstance(adventure_node, dict):
            return adventure_node
        return payload

    def _extract_image_style(self, payload: dict[str, Any], blueprint: dict[str, Any]) -> str:
        style_candidates = []
        for node in (blueprint, payload):
            selected_styles = node.get("selected_image_styles") if isinstance(node, dict) else None
            if isinstance(selected_styles, list):
                style_candidates.extend(selected_styles)

        style_names: list[str] = []
        for item in style_candidates:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("id") or "").strip()
            if name and name not in style_names:
                style_names.append(name)

        return ", ".join(style_names)

    def _collect_entities(self, payload: dict[str, Any], blueprint: dict[str, Any]) -> list[dict[str, str]]:
        entities: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for source in (payload, blueprint):
            extracted = []
            extracted.extend(self._extract_entities(source.get("scenes"), "scene", ("image_url",), ("description",)))
            extracted.extend(self._extract_entities(source.get("npcs"), "npc", ("profile_image", "image_url"), ("description",)))
            extracted.extend(self._extract_entities(source.get("items"), "object", ("image_url",), ("itemDescription", "description")))
            extracted.extend(self._extract_entities(source.get("objects"), "object", ("image_url",), ("itemDescription", "description")))

            for entity in extracted:
                dedupe_key = (entity["typ"], entity["id"])
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entities.append(entity)

        return entities

    def _extract_entities(
        self,
        nodes: Any,
        typ: str,
        image_keys: tuple[str, ...],
        description_keys: tuple[str, ...],
    ) -> list[dict[str, str]]:
        if not isinstance(nodes, list):
            return []

        result: list[dict[str, str]] = []
        for node in nodes:
            if not isinstance(node, dict):
                continue

            asset_id = str(node.get("id") or "").strip()
            name = str(node.get("name") or "").strip()
            image_ref = self._first_non_empty(node, image_keys)
            description = self._first_non_empty(node, description_keys)

            if not asset_id or not image_ref:
                continue

            result.append(
                {
                    "id": asset_id,
                    "name": name,
                    "description": description,
                    "typ": typ,
                    "image_ref": image_ref,
                }
            )

        return result

    def _first_non_empty(self, node: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _resolve_archive_member(self, image_ref: str, normalized_members: dict[str, str]) -> str | None:
        normalized = self._normalize_path(image_ref)
        if normalized in normalized_members:
            return normalized_members[normalized]

        basename = Path(normalized).name
        for member_normalized, original_name in normalized_members.items():
            if Path(member_normalized).name == basename:
                return original_name
        return None

    def _resolve_output_name(self, folder: Path, preferred_name: str) -> str:
        candidate = preferred_name
        stem = Path(preferred_name).stem
        suffix = Path(preferred_name).suffix

        counter = 1
        while (folder / candidate).exists():
            candidate = f"{stem}_{counter}{suffix}"
            counter += 1

        return candidate

    def _write_json(self, assets: list[ExtractedAsset]) -> None:
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        grouped: dict[str, list[dict[str, str]]] = {}
        for asset in assets:
            grouped.setdefault(asset.adventure, []).append(
                {
                    "filename": asset.filename,
                    "name": asset.name,
                    "description": asset.description,
                    "typ": asset.typ,
                    "image_style": asset.image_style,
                }
            )

        payload = [
            {
                "adventure": adventure,
                "assets": sorted(entries, key=lambda entry: (entry["typ"], entry["name"], entry["filename"])),
            }
            for adventure, entries in sorted(grouped.items(), key=lambda item: item[0].lower())
        ]

        self.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_adventure_json(self, adventure_dir: Path, all_records: list[ExtractedAsset]) -> None:
        adventure_name = adventure_dir.name
        entries = [
            {
                "filename": asset.filename,
                "name": asset.name,
                "description": asset.description,
                "typ": asset.typ,
                "image_style": asset.image_style,
            }
            for asset in all_records
            if self._sanitize_folder_name(asset.adventure) == adventure_name
        ]
        entries = sorted(entries, key=lambda entry: (entry["typ"], entry["name"], entry["filename"]))
        (adventure_dir / "metadata.json").write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_path(self, value: str) -> str:
        return value.replace("\\", "/").strip().lower()

    def _sanitize_folder_name(self, value: str) -> str:
        sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
        return sanitized or "adventure"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrahiert Bilder aus .adz-Dateien und erstellt eine JSON-Datei "
            "mit Dateiname und Kurzbeschreibung aus itemDescription."
        )
    )
    parser.add_argument("source_dir", type=Path, help="Quellordner mit .adz-Dateien")
    parser.add_argument("target_dir", type=Path, help="Zielordner fuer extrahierte Bilder")
    parser.add_argument(
        "output_json",
        type=Path,
        help="Ausgabe-JSON (z. B. data/metadata_all.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.source_dir.exists() or not args.source_dir.is_dir():
        print(f"Ungueltiger Quellordner: {args.source_dir}")
        return 1

    extractor = ADZAssetExtractor(args.source_dir, args.target_dir, args.output_json)
    return extractor.run()


if __name__ == "__main__":
    raise SystemExit(main())
