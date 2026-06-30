"""Persistent storage for editor validation runs.

One row per validation pass. Each run is scoped to a (template_id, user_id)
pair so multiple users working on the same adventure never see each other's
findings, and the editor can rehydrate the latest persisted snapshot on tab
open instead of forcing the user to re-run validation every time.
"""

import uuid6
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class ValidationRun(Base, TimestampMixin):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid6.uuid7()),
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("adventure_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    include_ai: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    structural_findings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    ai_findings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    ai_skipped_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    structural_finding_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    ai_finding_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    cached_suggestions: Mapped[Dict[str, Dict[str, Any]]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        doc="Per-finding AI fix proposals cache, keyed by finding_signature.",
    )
