"""LLM provider chain and suggestion cache for AI fixes."""

import asyncio
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.llm_router import GameMasterLLM
from backend.models.ai_fix_cache import AIFixCache
from backend.models.user import User

logger = logging.getLogger(__name__)


class _AIAttemptOutcome:
    """Outcome class for a single AI provider attempt."""

    SKIPPED_MISSING_KEY = "missing_key"
    SKIPPED_INIT_ERROR = "init_error"
    TIMEOUT = "timeout"
    CALL_ERROR = "call_error"

    def __init__(self, reason: str, *, provider: str, detail: str = "") -> None:
        self.reason = reason
        self.provider = provider
        self.detail = detail


class _AllProvidersFailedError(Exception):
    """Raised when every AI provider in the chain failed.

    The ``outcomes`` list records the reason each provider failed so the
    caller can craft a user-facing message tailored to the actual failure
    pattern (e.g. all-missing-keys vs all-timeouts).
    """

    def __init__(self, outcomes: list[_AIAttemptOutcome]) -> None:
        self.outcomes = outcomes
        summary = ", ".join(f"{o.provider}({o.reason})" for o in outcomes)
        super().__init__(f"All AI providers failed: {summary}")


def _summarize_outcomes(outcomes: list[_AIAttemptOutcome]) -> str:
    """Produce a short, anbieter-neutrale user-facing message."""
    if not outcomes:
        return "The AI service did not respond. Please retry in a moment."
    reasons = {o.reason for o in outcomes}
    if reasons == {_AIAttemptOutcome.SKIPPED_MISSING_KEY}:
        return (
            "No AI provider is fully configured with an API key. "
            "Please add one in the LLM provider settings, "
            "or ask an admin to set the AI_FIX_FALLBACK_PROVIDER."
        )
    if reasons == {_AIAttemptOutcome.TIMEOUT}:
        return "All AI providers are slow to respond right now. Please retry in a moment."
    return "The AI service is currently unavailable. Please retry in a moment."


def _candidate_attempts(current_user: User, allow_fallback: bool) -> list[tuple[str, str]]:
    """Distinct (provider, model) pairs: complex model, small model, then the admin fallback."""
    llm_settings = current_user.llm_settings or {}
    candidates = [
        (
            llm_settings.get("complex_model_provider"),
            llm_settings.get("complex_model") or "gpt-4o",
        ),
        (
            llm_settings.get("small_model_provider"),
            llm_settings.get("small_model") or "gpt-4o-mini",
        ),
    ]
    if allow_fallback:
        candidates.append(
            (settings.AI_FIX_FALLBACK_PROVIDER, settings.AI_FIX_FALLBACK_MODEL or None)
        )
    attempts: list[tuple[str, str]] = []
    for provider, model in candidates:
        candidate = (str(provider), str(model) if model else "")
        if provider and candidate not in attempts:
            attempts.append(candidate)
    return attempts or [("openai", "gpt-4o")]


def _init_provider(
    current_user: User, provider: str, model: str
) -> tuple[Optional[GameMasterLLM], Optional[_AIAttemptOutcome], Optional[Exception]]:
    """Build the provider client; on failure return the skip outcome instead."""
    try:
        gm = GameMasterLLM(user=current_user, provider=provider, model_category="complex")
    except ValueError as exc:
        logger.info(
            "Skipping AI provider '%s' (model '%s'): %s", provider, model or "<default>", exc
        )
        reason = _AIAttemptOutcome.SKIPPED_MISSING_KEY
        return None, _AIAttemptOutcome(reason, provider=provider, detail=str(exc)), exc
    except Exception as exc:
        logger.warning(
            "Skipping AI provider '%s' (model '%s'): %s", provider, model or "<default>", exc
        )
        reason = _AIAttemptOutcome.SKIPPED_INIT_ERROR
        return None, _AIAttemptOutcome(reason, provider=provider, detail=str(exc)), exc
    return gm, None, None


async def _call_provider(
    gm: GameMasterLLM,
    *,
    provider: str,
    model: str,
    user_prompt: str,
    response_model: type,
    gm_kwargs: dict[str, Any],
    timeout_seconds: Optional[float],
) -> Any:
    """One LLM call; a timeout is re-raised as ``TimeoutError`` naming the provider."""
    coro = gm.aexecute_complex_task(
        system_prompt=gm_kwargs["system_prompt"],
        user_prompt=user_prompt,
        response_model=response_model,
        model=model,
    )
    try:
        if timeout_seconds and timeout_seconds > 0:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        return await coro
    except asyncio.TimeoutError as exc:
        cap = timeout_seconds or 0
        raise TimeoutError(f"AI request to '{provider}' exceeded the {cap:.0f}s cap") from exc


def _call_failure_outcome(
    exc: Exception, provider: str, model: str, timeout_seconds: Optional[float]
) -> _AIAttemptOutcome:
    if isinstance(exc, TimeoutError):
        logger.warning(
            "AI call to '%s' (model '%s') timed out after %.0fs",
            provider,
            model,
            timeout_seconds or 0,
        )
        return _AIAttemptOutcome(_AIAttemptOutcome.TIMEOUT, provider=provider, detail=str(exc))
    logger.warning("AI call to '%s' (model '%s') raised: %s", provider, model, exc)
    return _AIAttemptOutcome(_AIAttemptOutcome.CALL_ERROR, provider=provider, detail=str(exc))


async def _generate_llm_proposals(
    *,
    user_prompt: str,
    current_user: User,
    response_model: type,
    gm_kwargs: dict[str, Any],
    timeout_seconds: Optional[float] = None,
    allow_fallback: bool = True,
) -> tuple[Any, Optional[str]]:
    """Call the LLM with a hard wall-clock cap and an optional fallback chain.

    Builds a candidate list straight from ``user.llm_settings``:

    1. ``complex_model_provider`` / ``complex_model`` (best reasoning).
    2. ``small_model_provider`` / ``small_model`` (typically small, fast).
    3. ``AI_FIX_FALLBACK_PROVIDER`` / ``AI_FIX_FALLBACK_MODEL`` env defaults.

    Each candidate is tried in order; provider construction errors
    (missing API key, configuration problems, ...) and per-call timeouts
    cause the next candidate to take over. The first success wins.

    Returns ``(response, provider_label)``.

    On total failure, raises ``_AllProvidersFailedError`` whose ``outcomes`` list
    captures the reason for each skipped/timed-out provider. Callers use
    this to decide whether to surface "no provider configured" vs
    "all timeouts" vs "generic unavailable" to the user. When the last
    candidate's call itself fails, that error (or a ``TimeoutError``) is raised.
    """
    attempts = _candidate_attempts(current_user, allow_fallback)
    outcomes: list[_AIAttemptOutcome] = []
    last_error: Optional[Exception] = None
    for idx, (provider, model) in enumerate(attempts):
        gm, skipped, init_error = _init_provider(current_user, provider, model)
        if gm is None or skipped is not None:
            outcomes.append(skipped)  # type: ignore[arg-type]
            last_error = init_error
            continue
        try:
            result = await _call_provider(
                gm,
                provider=provider,
                model=model,
                user_prompt=user_prompt,
                response_model=response_model,
                gm_kwargs=gm_kwargs,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            last_error = exc
            outcomes.append(_call_failure_outcome(exc, provider, model, timeout_seconds))
            if idx == len(attempts) - 1:
                raise
            continue
        return result, provider

    if outcomes:
        logger.info(
            "All %d AI provider attempt(s) failed for user '%s'; reasons=%s",
            len(outcomes),
            current_user.username,
            ";".join(f"{o.provider}({o.reason})" for o in outcomes),
        )
    if last_error is not None:
        raise _AllProvidersFailedError(outcomes) from last_error
    return None, None


AIFIX_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


async def _get_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
) -> Optional[dict[str, Any]]:
    from datetime import datetime, timezone

    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    row = res.scalars().first()
    if row is None:
        return None
    expires = row.expires_at
    if expires is not None:
        now = datetime.now(timezone.utc)
        compare_to = expires if expires.tzinfo else expires.replace(tzinfo=timezone.utc)
        if compare_to < now:
            try:
                await db.delete(row)
                await db.commit()
            except Exception:
                await db.rollback()
            return None
    return dict(row.response or {})


async def _write_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
    response_payload: dict[str, Any],
) -> None:
    from datetime import datetime, timedelta, timezone

    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    row = res.scalars().first()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=AIFIX_CACHE_TTL_SECONDS)
    if row is None:
        row = AIFixCache(
            template_id=template_id,
            user_id=user_id,
            finding_signature=signature,
            response=response_payload,
            expires_at=expires_at,
        )
        db.add(row)
    else:
        row.response = response_payload
        row.expires_at = expires_at
    try:
        await db.commit()
    except Exception:
        await db.rollback()


async def _evict_cached_suggestions(
    *,
    db: AsyncSession,
    template_id: str,
    user_id: str,
    signature: str,
) -> None:
    res = await db.execute(
        select(AIFixCache).where(
            AIFixCache.template_id == template_id,
            AIFixCache.user_id == user_id,
            AIFixCache.finding_signature == signature,
        )
    )
    for row in res.scalars().all():
        try:
            await db.delete(row)
        except Exception as exc:
            logger.warning("Failed to evict AI fix cache row: %s", exc)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
