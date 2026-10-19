"""Applies validated world manifests (generated, imported or edited) to the database."""

from backend.engine.manifest_apply.apply import apply_manifest

__all__ = ["apply_manifest"]
