"""Script editor AI assistant: optimizes or generates a script / guard for one editor field.

The result is only a proposal: the editor shows it as a diff and the author accepts or
discards it, so nothing is saved here. Every proposal runs through the sandbox syntax
check; a failing one gets a single repair round with the errors before it is returned.
"""

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.ai_fix_context import (
    _format_world_context_block,
    _summarize_world_for_fix,
)
from backend.api.routes.adventures.editing.ai_fix_llm import (
    _AllProvidersFailedError,
    _generate_llm_proposals,
    _summarize_outcomes,
)
from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.payload import _build_adventure_editor_assets
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.script_assist_prompts import (
    SCRIPT_ASSIST_SYSTEM_PROMPT,
    describe_context,
    mode_instructions,
)
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.models.user import User
from backend.schemas.script_assist import ScriptAssistRequest, ScriptAssistResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

_EXPRESSION_CONTEXT = "guard_expression"
_INIT_SCRIPT_PROMPT_MAX = 3000
_SUMMARY_MAX = 600
_CODE_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", re.DOTALL)
_MISSING_INSTRUCTION = "Describe what the code should do."
_EMPTY_RESULT = "The AI did not return any code. Please try again."
_TIMEOUT_MESSAGE = "The AI service did not respond in time. Please retry in a moment."
_UNAVAILABLE_MESSAGE = "The AI service is currently unavailable. Please retry in a moment."


class _ScriptAssistLLMResponse(BaseModel):
    code: str = ""
    summary: str = ""


def _clean_code(code: str) -> str:
    """Removes a markdown fence the model may wrap the code in."""
    match = _CODE_FENCE.match(code or "")
    return (match.group(1) if match else code or "").strip("\n")


def syntax_errors(code: str, context: str) -> list[str]:
    """Sandbox check matching the editor field (guard expression or script)."""
    if context == _EXPRESSION_CONTEXT:
        return SafeAstInterpreter.check_expression_syntax(code)
    return SafeAstInterpreter.check_syntax(code)


def _init_script_block(assets: Any) -> str:
    adventure = getattr(assets, "adventure", None) or {}
    init_script = str(adventure.get("init_script") or "").strip()
    if not init_script:
        return ""
    return (
        "=== INIT SCRIPT (helper functions and constants every script may call) ===\n"
        f"{init_script[:_INIT_SCRIPT_PROMPT_MAX]}\n\n"
    )


def _user_prompt(payload: ScriptAssistRequest, assets: Any) -> str:
    kind = "guard expression" if payload.context == _EXPRESSION_CONTEXT else "script"
    hint = payload.instruction.strip()
    return (
        f"{_format_world_context_block(_summarize_world_for_fix(assets))}\n"
        f"{_init_script_block(assets)}"
        f"=== EDITOR FIELD ===\n{describe_context(payload.context, payload.label)}\n"
        f"The code is a {kind}.\n\n"
        f"=== TASK ===\n{mode_instructions(payload.mode)}\n\n"
        f"=== CURRENT CODE ===\n```python\n{payload.code}\n```\n\n"
        f"=== AUTHOR {'INSTRUCTION' if payload.mode == 'generate' else 'HINT'} ===\n"
        f'"""\n{hint or "(none)"}\n"""\n\n'
        "Return ONLY the JSON object with 'code' and 'summary'."
    )


def _repair_prompt(prompt: str, code: str, errors: list[str]) -> str:
    listed = "\n".join(f"- {e}" for e in errors)
    return (
        f"{prompt}\n\n=== YOUR PREVIOUS PROPOSAL FAILED THE SANDBOX CHECK ===\n"
        f"```python\n{code}\n```\nErrors:\n{listed}\n"
        "Fix these errors and return the complete corrected code."
    )


async def _ask(prompt: str, current_user: User) -> _ScriptAssistLLMResponse:
    result, _provider = await _generate_llm_proposals(
        user_prompt=prompt,
        current_user=current_user,
        response_model=_ScriptAssistLLMResponse,
        gm_kwargs={"system_prompt": SCRIPT_ASSIST_SYSTEM_PROMPT},
        timeout_seconds=settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS,
        allow_fallback=True,
    )
    result = result or _ScriptAssistLLMResponse()
    result.code = _clean_code(result.code)
    return result


def _failure_message(exc: Exception, template_id: str) -> str:
    if isinstance(exc, _AllProvidersFailedError):
        logger.warning("Script assist unavailable for %s: %s", template_id, exc)
        return _summarize_outcomes(exc.outcomes)
    if isinstance(exc, TimeoutError):
        logger.warning("Script assist timed out for %s: %s", template_id, exc)
        return _TIMEOUT_MESSAGE
    logger.exception("Script assist failed for %s: %s", template_id, exc)
    return _UNAVAILABLE_MESSAGE


async def _propose(
    payload: ScriptAssistRequest, assets: Any, current_user: User
) -> ScriptAssistResponse:
    prompt = _user_prompt(payload, assets)
    result = await _ask(prompt, current_user)
    errors = syntax_errors(result.code, payload.context)
    if errors and result.code.strip():
        result = await _ask(_repair_prompt(prompt, result.code, errors), current_user)
        errors = syntax_errors(result.code, payload.context)
    if not result.code.strip():
        return ScriptAssistResponse(error=_EMPTY_RESULT)
    return ScriptAssistResponse(
        code=result.code,
        summary=result.summary.strip()[:_SUMMARY_MAX] or None,
        syntax_errors=errors,
    )


@router.post("/{template_id}/editor/scripts/assist", response_model=ScriptAssistResponse)
async def script_assist(
    template_id: str,
    payload: ScriptAssistRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proposes optimized or generated code for one editor field (HTTP 200 with ``error``)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    if payload.mode == "generate" and not payload.instruction.strip():
        return ScriptAssistResponse(error=_MISSING_INSTRUCTION)
    assets = await _build_adventure_editor_assets(template_id, db)
    try:
        return await _propose(payload, assets, current_user)
    except Exception as exc:
        return ScriptAssistResponse(error=_failure_message(exc, template_id))
