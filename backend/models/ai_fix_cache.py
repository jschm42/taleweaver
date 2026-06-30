"""Per-(template, user, finding) cache for AI-generated fix proposals.

Each row holds the most recent AIFixSuggestionsResponse for a given
``(template_id, user_id, finding_signature)`` triple. The cache is the
fast path of the AI-fix-suggestion endpoint: a repeat click on the same
finding returns instantly without a second LLM call.

Invalidation:
* Any new structural / AI validation run writes a fresh row (with empty
  ``cached_suggestions``) so the *old* cache entry remains queryable by
  the user for the rest of their session.
* ``POST /validate/findings/apply-fix`` deletes the cache row for the
  applied finding signature, because the world state has changed.
"""

import uuid6
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class AIFixCache(Base, TimestampMixin):
    __tablename__ = "ai_fix_cache"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid6.uuid7()),
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("adventure_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_signature: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
    )
    response: Mapped[Dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
