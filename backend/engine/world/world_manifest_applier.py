"""Backward-compatible import path for the manifest applier (see ``backend.engine.manifest_apply``)."""

from backend.engine.manifest_apply.apply import apply_manifest
from backend.engine.manifest_apply.scenes import persist_exits as _persist_exits

__all__ = ["_persist_exits", "apply_manifest"]
