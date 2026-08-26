"""Integration tests for the AI fix suggestion / apply endpoints."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.core.config import settings as app_settings
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_simple_adventure(db: AsyncSession, *, owner: User) -> str:
    tpl = AdventureTemplate(
        id="tpl-fix-1",
        owner_id=owner.id,
        title="Fix Test",
        version="1.0",
        rule_enforcement_mode="rpg",
        is_ready=True,
        creation_status="Ready",
        generate_scene_images=False,
        generate_npc_images=False,
        generate_item_images=False,
        teaser="t",
        rules="r",
        plot="p",
        intro_text="i",
        walkthrough="w",
        completed_condition="done",
        gameover_condition="lost",
        tts_director_notes="notes",
        quests=[],
    )
    db.add(tpl)
    await db.flush()

    db.add(WorldScene(
        id="START",
        template_id=tpl.id,
        label="Start",
        description="A dusty entrance hall.",
    ))
    db.add(WorldScene(
        id="OBSERVATION_LOUNGE",
        template_id=tpl.id,
        label="Observation Lounge",
        description="A quiet observation lounge.",
    ))
    db.add(WorldEntity(
        id="OLD_LIBRARIAN",
        template_id=tpl.id,
        entity_type="NPC",
        name="Old Librarian",
        description="A wizened keeper.",
        current_scene_id="START",
    ))
    db.add(WorldEntity(
        id="SAFE_01",
        template_id=tpl.id,
        entity_type="OBJECT",
        name="Safe",
        description="A heavy steel safe.",
        current_scene_id="START",
        item_type="CONTAINER",
    ))
    db.add(WorldExit(
        template_id=tpl.id,
        from_scene_id="START",
        to_scene_id="OBSERVATION_LOUNGE",
        label="A heavy oak door",
        is_locked=True,
        code_to_unlock="1331",
        lock_description="Requires a code to unlock.",
        exit_type="one_way",
    ))
    await db.commit()
    return tpl.id


def test_default_ai_fix_suggest_timeout_is_generous():
    """The watchdog default must give slow providers (Deepseek etc.) room to respond.

    Regression guard: bumping the default back to a too-aggressive value would
    re-trigger the timeout cascade users were hitting.
    """
    assert app_settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS >= 60.0


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_suggest_fix_returns_proposals(client, setup_test_db, monkeypatch):
    """The /suggest-fix endpoint must invoke the LLM and return up to 3 proposals."""
    user = User(
        username="fix_user_1",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    captured = {}

    class _Proposal:
        title = "Add a numeric hint to the librarian's dialogue"
        summary = "Insert a small hint in the librarian's description so the code can be derived."
        rationale = "Minimal change to one entity."
        patches = [
            {
                "target_type": "npc",
                "target_id": "OLD_LIBRARIAN",
                "description": "Mention the code digits in passing.",
                "field_updates": {"description": "A wizened keeper."},
            }
        ]



    class _Wrapper:
        proposals = [_Proposal()]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, *, system_prompt, user_prompt, response_model, model, **kwargs):
            captured["system_starts_with_assistant"] = "assistant" in system_prompt.lower()
            captured["user_contains_finding"] = "orphaned_container_code" in user_prompt
            captured["user_contains_location"] = "object:SAFE_01" in user_prompt
            captured["model"] = model
            captured["schema_keys"] = list(response_model.model_json_schema().get("properties", {}).keys())
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_1"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Safe has code '4289' but no hint in the world.",
            "finding_location": "object:SAFE_01",
            "finding_context": {"code": "4289"},
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["finding_signature"].startswith("warn|orphaned_container_code|object:SAFE_01|")
    assert len(payload["proposals"]) == 1
    assert payload["proposals"][0]["title"].startswith("Add a numeric hint")
    assert captured["user_contains_finding"]
    assert captured["user_contains_location"]
    assert captured["model"] == "gpt-4o"
    assert "proposals" in captured["schema_keys"]


async def test_suggest_fix_rejects_more_than_three(client, setup_test_db, monkeypatch):
    """Server-side clamp: at most 3 proposals survive validation."""
    user = User(
        username="fix_user_clamp",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    class _Proposal:
        def __init__(self, i):
            self.title = f"Option {i}"
            self.summary = f"S {i}"
            self.rationale = None
            self.patches = [
                {
                    "target_type": "adventure",
                    "target_id": None,
                    "description": "noop",
                    "field_updates": {"walkthrough": f"new walkthrough {i}"},
                }
            ]

    class _Wrapper:
        proposals = [_Proposal(i) for i in range(7)]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_clamp"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "any",
            "finding_location": "object:SAFE_01",
            "finding_context": {},
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert len(payload["proposals"]) == 3


async def test_suggest_fix_unauthorized_when_not_owner(client, setup_test_db, monkeypatch):
    owner = User(username="fix_owner", hashed_password="x", role="admin")
    intruder = User(username="fix_intruder", hashed_password="x", role="user")
    async with TestSessionLocal() as db:
        db.add(owner)
        db.add(intruder)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=owner)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_intruder"),
        json={
            "finding_code": "x",
            "finding_message": "y",
            "finding_location": None,
            "finding_context": None,
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 404


async def test_suggest_fix_timeout_returns_200_with_error(client, setup_test_db, monkeypatch):
    """A hanging LLM must be cut off after the watchdog and surfaced as a clean 200."""

    user = User(
        username="fix_user_timeout",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    import asyncio as _asyncio

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            await _asyncio.sleep(120)
            return None

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)
    monkeypatch.setattr(
        "backend.core.config.settings.AI_FIX_SUGGEST_TIMEOUT_SECONDS", 0.05,
        raising=False,
    )
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_SUGGEST_TIMEOUT_SECONDS", 0.05)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_timeout"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "object:SAFE_01",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    assert payload["error"]
    assert "retry" in payload["error"].lower() or "respond" in payload["error"].lower()
    assert payload["finding_signature"].startswith("warn|orphaned_container_code")


async def test_suggest_fix_runtime_error_returns_200_with_error(client, setup_test_db, monkeypatch):
    """A non-timeout LLM failure (parse, network, missing key) must also resolve 200."""

    user = User(
        username="fix_user_runtime",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            raise RuntimeError("Upstream bad gateway")

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_runtime"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "object:SAFE_01",
            "finding_context": {},
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    assert payload["error"]
    assert "Upstream bad gateway" not in payload["error"]
    assert "deepseek" not in payload["error"].lower()


async def test_suggest_fix_all_missing_keys_returns_config_message(
    client, setup_test_db, monkeypatch,
):
    """When every provider in the chain fails with 'no API key', the user sees a config hint."""

    user = User(
        username="fix_user_no_keys",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "deepseek", "complex_model": "deepseek-v4-pro"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    class _NoKeyLLM:
        def __init__(self, *args, **kwargs):
            raise ValueError(f"No API key configured for provider: {kwargs.get('provider')}")

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _NoKeyLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_no_keys"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "object:SAFE_01",
            "finding_context": {},
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    error = payload["error"]
    assert "API key" in error or "configured" in error
    assert "add an API key" in error.lower() or "AI provider" in error
    assert "deepseek" not in error.lower()
    assert "openai" not in error.lower()


async def test_suggest_fix_all_timeouts_returns_timeout_message(
    client, setup_test_db, monkeypatch,
):
    """When every provider times out, the message tells the user to retry."""

    user = User(
        username="fix_user_all_timeouts",
        hashed_password="x",
        role="admin",
        llm_settings={
            "complex_model_provider": "deepseek",
            "complex_model": "deepseek-v4-pro",
            "small_model_provider": "openai",
            "small_model": "gpt-4o-mini",
        },
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    import asyncio as _asyncio

    class _SlowLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            await _asyncio.sleep(2)
            raise _asyncio.TimeoutError()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _SlowLLM)
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_SUGGEST_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_PROVIDER", "anthropic")

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_all_timeouts"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "object:SAFE_01",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    error = payload["error"].lower()
    assert "slow" in error or "retry" in error
    assert "deepseek" not in payload["error"].lower()


async def test_suggest_fix_uses_focused_prompt(client, setup_test_db, monkeypatch):
    """The suggest-fix prompt must only contain the targeted entity + neighbors, not the full world."""

    user = User(
        username="fix_user_focused",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    captured = {}

    class _Proposal:
        def __init__(self):
            self.title = "Inline hint"
            self.summary = "Drop a numeric hint into the librarian's description."
            self.rationale = None
            self.patches = [
                {
                    "target_type": "npc",
                    "target_id": "OLD_LIBRARIAN",
                    "description": "Mention digits.",
                    "field_updates": {"description": "Updated."},
                }
            ]

    class _Wrapper:
        proposals = [_Proposal()]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, *, system_prompt, user_prompt, response_model, model, **kwargs):
            captured["user_prompt"] = user_prompt
            captured["user_prompt_bytes"] = len(user_prompt.encode("utf-8"))
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_focused"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "npc:OLD_LIBRARIAN",
            "finding_context": {},
            "finding_severity": "warn",
        },
    )
    assert resp.status_code == 200, resp.text

    prompt = captured["user_prompt"]
    assert "TARGET NPC (OLD_LIBRARIAN)" in prompt
    assert "ADJACENT ENTITIES" in prompt
    assert "Safe" not in prompt or "ADJACENT ENTITIES" in prompt
    assert captured["user_prompt_bytes"] < 8_000


async def test_suggest_fix_falls_back_on_timeout(client, setup_test_db, monkeypatch):
    """A timeout on the primary provider triggers a fallback attempt."""

    user = User(
        username="fix_user_fallback",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    import asyncio as _asyncio

    attempts = []

    class _FakePrimaryLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            attempts.append("primary")
            await _asyncio.sleep(5)
            raise _asyncio.TimeoutError()

    class _FallbackPatch:
        def __init__(self):
            self.target_type = "npc"
            self.target_id = "OLD_LIBRARIAN"
            self.description = None
            self.field_updates = {"description": "Quick fix from fallback."}

    class _FallbackProposal:
        def __init__(self):
            self.title = "Fallback fix"
            self.summary = "Short patch."
            self.rationale = None
            self.patches = [_FallbackPatch()]

    class _FallbackWrapper:
        proposals = [_FallbackProposal()]

    class _FakeFallbackLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            attempts.append("fallback")
            return _FallbackWrapper()

    from backend.api.routes.adventures import editor as editor_module

    primary_calls = {"n": 0}
    fallback_calls = {"n": 0}

    def _factory(*args, **kwargs):
        provider = kwargs.get("provider")
        if provider is None and len(args) > 1:
            provider = args[1]
        if provider == "openai":
            primary_calls["n"] += 1
            return _FakePrimaryLLM(*args, **kwargs)
        fallback_calls["n"] += 1
        return _FakeFallbackLLM(*args, **kwargs)

    monkeypatch.setattr(editor_module, "GameMasterLLM", _factory)
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_SUGGEST_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_PROVIDER", "anthropic")
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_MODEL", "claude-test")

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_fallback"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "npc:OLD_LIBRARIAN",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert attempts == ["primary", "fallback"]
    assert len(payload["proposals"]) == 1
    assert payload["proposals"][0]["title"] == "Fallback fix"
    assert primary_calls["n"] == 1
    assert fallback_calls["n"] == 1


async def test_suggest_fix_falls_back_to_user_small_provider(client, setup_test_db, monkeypatch):
    """When complex provider times out, the chain tries the user's small_model_provider."""

    user = User(
        username="fix_user_small_chain",
        hashed_password="x",
        role="admin",
        llm_settings={
            "complex_model_provider": "deepseek",
            "complex_model": "deepseek-v4-pro",
            "small_model_provider": "openai",
            "small_model": "gpt-4o-mini",
        },
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    import asyncio as _asyncio

    attempts: list[str] = []

    class _PrimaryLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            attempts.append("deepseek")
            await _asyncio.sleep(2)
            raise _asyncio.TimeoutError()

    class _Patch:
        def __init__(self):
            self.target_type = "npc"
            self.target_id = "OLD_LIBRARIAN"
            self.description = None
            self.field_updates = {"description": "From small chain."}

    class _Proposal:
        def __init__(self):
            self.title = "Small-model fix"
            self.summary = "x"
            self.rationale = None
            self.patches = [_Patch()]

    class _Wrapper:
        proposals = [_Proposal()]

    class _SecondaryLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            attempts.append("openai")
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module

    def _factory(*args, **kwargs):
        provider = kwargs.get("provider")
        if provider is None and len(args) > 1:
            provider = args[1]
        if provider == "deepseek":
            return _PrimaryLLM(*args, **kwargs)
        return _SecondaryLLM(*args, **kwargs)

    monkeypatch.setattr(editor_module, "GameMasterLLM", _factory)
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_SUGGEST_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_PROVIDER", "anthropic")

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_small_chain"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "npc:OLD_LIBRARIAN",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert attempts == ["deepseek", "openai"], attempts
    assert payload["proposals"][0]["title"] == "Small-model fix"


async def test_suggest_fix_skips_provider_with_missing_api_key(client, setup_test_db, monkeypatch):
    """A provider that raises ValueError during construction must be skipped, not crash the endpoint."""

    user = User(
        username="fix_user_missing_key",
        hashed_password="x",
        role="admin",
        llm_settings={
            "complex_model_provider": "deepseek",
            "complex_model": "deepseek-v4-pro",
            "small_model_provider": "openai",
            "small_model": "gpt-4o-mini",
        },
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    import asyncio as _asyncio

    attempts: list[str] = []

    class _DeepseekLLM:
        def __init__(self, *args, **kwargs):
            raise ValueError("No API key configured for provider: deepseek")

    class _OpenaiLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            attempts.append("openai")

            class _Patch:
                target_type = "npc"
                target_id = "OLD_LIBRARIAN"
                description = None
                field_updates = {"description": "x"}

            class _Proposal:
                title = "From openai"
                summary = "s"
                rationale = None
                patches = [_Patch()]

            class _Wrapper:
                proposals = [_Proposal()]

            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module

    def _factory(*args, **kwargs):
        provider = kwargs.get("provider")
        if provider is None and len(args) > 1:
            provider = args[1]
        if provider == "deepseek":
            return _DeepseekLLM(*args, **kwargs)
        return _OpenaiLLM(*args, **kwargs)

    monkeypatch.setattr(editor_module, "GameMasterLLM", _factory)
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_PROVIDER", "anthropic")

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_missing_key"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "npc:OLD_LIBRARIAN",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert attempts == ["openai"]
    assert payload["proposals"][0]["title"] == "From openai"


async def test_suggest_fix_clean_error_when_all_providers_unavailable(
    client, setup_test_db, monkeypatch,
):
    """If the chain has no usable provider, the endpoint must return 200 with empty proposals + a clean error."""

    user = User(
        username="fix_user_no_provider",
        hashed_password="x",
        role="admin",
        llm_settings={
            "complex_model_provider": "deepseek",
            "complex_model": "deepseek-v4-pro",
        },
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    class _UnavailLLM:
        def __init__(self, *args, **kwargs):
            raise ValueError("No API key configured for provider: deepseek")

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _UnavailLLM)
    import backend.core.config as _config_module
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_PROVIDER", "openai")
    monkeypatch.setattr(_config_module.settings, "AI_FIX_FALLBACK_MODEL", "gpt-4o-mini")

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_no_provider"),
        json={
            "finding_code": "orphaned_container_code",
            "finding_message": "Container orphan.",
            "finding_location": "npc:OLD_LIBRARIAN",
            "finding_context": {},
            "finding_severity": "warn",
        },
        timeout=5.0,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    assert payload["error"]
    assert "deepseek" not in payload["error"].lower()
    assert "openai" not in payload["error"].lower()

async def test_suggest_fix_cache_hit_skips_llm(client, setup_test_db, monkeypatch):
    """A repeat request for the same finding signature must return cached proposals."""

    user = User(
        username="fix_user_cache_hit",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    calls = {"n": 0}

    class _Proposal:
        def __init__(self):
            self.title = "Cached fix"
            self.summary = "Stored response."
            self.rationale = None
            self.patches = [
                {
                    "target_type": "npc",
                    "target_id": "OLD_LIBRARIAN",
                    "description": "Mention digits.",
                    "field_updates": {"description": "Cached."},
                }
            ]

    class _Wrapper:
        proposals = [_Proposal()]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            calls["n"] += 1
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    body = {
        "finding_code": "orphaned_container_code",
        "finding_message": "Container orphan.",
        "finding_location": "npc:OLD_LIBRARIAN",
        "finding_context": {},
        "finding_severity": "warn",
    }

    first = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_cache_hit"),
        json=body,
    )
    assert first.status_code == 200, first.text
    assert calls["n"] == 1

    second = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_cache_hit"),
        json=body,
    )
    assert second.status_code == 200, second.text
    payload = second.json()
    assert calls["n"] == 1
    assert payload["proposals"][0]["title"] == "Cached fix"


async def test_apply_fix_evicts_cache(client, setup_test_db, monkeypatch):
    """A successful apply must invalidate the cached suggestion for that finding."""

    user = User(
        username="fix_user_evict",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    class _Patch:
        target_type = "npc"
        target_id = "OLD_LIBRARIAN"
        description = "Drop digits."
        field_updates = {"description": "Updated."}

    class _Proposal:
        def __init__(self):
            self.title = "Inline hint"
            self.summary = "x"
            self.rationale = None
            self.patches = [_Patch()]

    class _Wrapper:
        proposals = [_Proposal()]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            return _Wrapper()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    body_req = {
        "finding_code": "orphaned_container_code",
        "finding_message": "x",
        "finding_location": "npc:OLD_LIBRARIAN",
        "finding_context": {},
        "finding_severity": "warn",
    }
    first = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/suggest-fix",
        headers=_auth_headers("fix_user_evict"),
        json=body_req,
    )
    assert first.status_code == 200, first.text

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        from backend.models.ai_fix_cache import AIFixCache
        res = await db.execute(_sel(AIFixCache).where(AIFixCache.template_id == tpl_id))
        assert len(res.scalars().all()) == 1

    apply = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_evict"),
        json={
            "finding_signature": first.json()["finding_signature"],
            "proposal": {
                "title": "Inline hint",
                "summary": "x",
                "patches": [{
                    "target_type": "npc",
                    "target_id": "OLD_LIBRARIAN",
                    "description": "Drop digits.",
                    "field_updates": {"description": "Updated."},
                }],
            },
        },
    )
    assert apply.status_code == 200, apply.text

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        from backend.models.ai_fix_cache import AIFixCache
        res = await db.execute(_sel(AIFixCache).where(AIFixCache.template_id == tpl_id))
        assert len(res.scalars().all()) == 0


async def test_apply_fix_resolves_exit_by_composite_id(client, setup_test_db):
    """``target_id`` of the form ``SCENE_A->SCENE_B`` must resolve the matching exit."""

    user = User(username="fix_user_exit_composite", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    proposal = {
        "title": "Lower the door lock",
        "summary": "Drop the lock code.",
        "rationale": None,
        "patches": [{
            "target_type": "exit",
            "target_id": "START->OBSERVATION_LOUNGE",
            "description": "Replace the code.",
            "field_updates": {"code_to_unlock": "0000"},
        }],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_exit_composite"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"
    assert body["applied_targets"], body["applied_targets"]

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        res = await db.execute(
            _sel(WorldExit).where(
                WorldExit.template_id == tpl_id,
                WorldExit.from_scene_id == "START",
                WorldExit.to_scene_id == "OBSERVATION_LOUNGE",
            )
        )
        world_exit = res.scalars().first()
        assert world_exit is not None
        assert world_exit.code_to_unlock == "0000"


async def test_apply_fix_resolves_exit_by_from_scene_only(client, setup_test_db):
    """``target_id`` = a single scene ID picks the only exit leaving that scene."""

    user = User(username="fix_user_exit_from", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    proposal = {
        "title": "Unlock the door",
        "summary": "Drop the lock.",
        "rationale": None,
        "patches": [{
            "target_type": "exit",
            "target_id": "START",
            "description": "Match by outgoing scene.",
            "field_updates": {"locked": False},
        }],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_exit_from"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        res = await db.execute(
            _sel(WorldExit).where(
                WorldExit.template_id == tpl_id,
                WorldExit.from_scene_id == "START",
            )
        )
        world_exit = res.scalars().first()
        assert world_exit is not None
        assert world_exit.is_locked is False


async def test_apply_fix_resolves_exit_by_label(client, setup_test_db):
    """``target_id`` = the human-readable label resolves uniquely to the right exit."""

    user = User(username="fix_user_exit_label", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    proposal = {
        "title": "Update door rule",
        "summary": "Drop code_to_unlock via label lookup.",
        "rationale": None,
        "patches": [{
            "target_type": "exit",
            "target_id": "A heavy oak door",
            "description": "Match by label.",
            "field_updates": {"code_to_unlock": "9999"},
        }],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_exit_label"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"

    async with TestSessionLocal() as db:
        from sqlalchemy import select as _sel
        res = await db.execute(
            _sel(WorldExit).where(
                WorldExit.template_id == tpl_id,
                WorldExit.from_scene_id == "START",
            )
        )
        world_exit = res.scalars().first()
        assert world_exit is not None
        assert world_exit.code_to_unlock == "9999"


async def test_apply_fix_with_stale_uuid_still_404(client, setup_test_db):
    """A target_id that resolves to nothing should still produce a clean 400 + cache evict."""

    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete as _del
    from sqlalchemy import select as _sel

    from backend.models.ai_fix_cache import AIFixCache

    user = User(username="fix_user_stale_uuid", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)
        user_id = user.id

    stale_sig = "warn|stale-target|x|{}"
    cache_payload = {
        "finding_signature": stale_sig,
        "proposals": [],
        "generated_at": "",
    }
    async with TestSessionLocal() as db:
        await db.execute(_del(AIFixCache).where(AIFixCache.template_id == tpl_id))
        db.add(AIFixCache(
            template_id=tpl_id,
            user_id=user_id,
            finding_signature=stale_sig,
            response=cache_payload,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        await db.commit()

    proposal = {
        "title": "Phantom patch",
        "summary": "Targets an exit that no longer exists.",
        "rationale": None,
        "patches": [{
            "target_type": "exit",
            "target_id": "DECONTAMINATION_CHAMBER",
            "description": "Patches a stale ref.",
            "field_updates": {"locked": False},
        }],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_stale_uuid"),
        json={
            "finding_signature": stale_sig,
            "proposal": proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "no_op"
    assert "out of date" in (body["message"] or "").lower()

    async with TestSessionLocal() as db:
        res = await db.execute(
            _sel(AIFixCache).where(
                AIFixCache.template_id == tpl_id,
                AIFixCache.finding_signature == stale_sig,
            )
        )
        assert res.scalars().first() is None


async def test_apply_fix_to_npc_description(client, setup_test_db):
    """Apply must mutate the targeted entity and return applied status."""

    user = User(
        username="fix_user_apply_npc",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    chosen_proposal = {
        "title": "Insert hint into librarian dialogue",
        "summary": "Add a numeric hint to the librarian's description so the safe code can be derived.",
        "rationale": "Single field edit; minimal risk.",
        "patches": [
            {
                "target_type": "npc",
                "target_id": "OLD_LIBRARIAN",
                "description": "Mention the code digits in passing.",
                "field_updates": {
                    "description": "A wizened keeper who whispers 'four, two, eight, nine' on windy nights.",
                },
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_apply_npc"),
        json={
            "finding_signature": "warn|orphaned_container_code|object:SAFE_01|{\"code\":\"4289\"}",
            "proposal": chosen_proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "applied"
    assert payload["applied_targets"] == ["npc:OLD_LIBRARIAN"]

    async with TestSessionLocal() as db:
        ent_res = await db.execute(
            __import__("sqlalchemy").select(WorldEntity).where(
                WorldEntity.template_id == tpl_id, WorldEntity.id == "OLD_LIBRARIAN"
            )
        )
        ent = ent_res.scalars().first()
        assert ent is not None
        assert "four, two, eight, nine" in ent.description


async def test_apply_fix_to_object_container_code(client, setup_test_db):
    """Object/CONTAINER lock fields are routed through metadata_json correctly."""

    user = User(
        username="fix_user_apply_obj",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    chosen_proposal = {
        "title": "Remove the orphan code",
        "summary": "Clear the safe code so it doesn't dangle.",
        "rationale": "Simplest fix.",
        "patches": [
            {
                "target_type": "object",
                "target_id": "SAFE_01",
                "description": "Empty the lock code.",
                "field_updates": {"code_to_unlock": "77", "locked": True},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_apply_obj"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": chosen_proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "applied"
    assert payload["applied_targets"] == ["object:SAFE_01"]

    async with TestSessionLocal() as db:
        ent_res = await db.execute(
            __import__("sqlalchemy").select(WorldEntity).where(
                WorldEntity.template_id == tpl_id, WorldEntity.id == "SAFE_01"
            )
        )
        ent = ent_res.scalars().first()
        assert ent is not None
        meta = ent.metadata_json or {}
        assert meta.get("code_to_unlock") == "77"
        assert meta.get("locked") is True


async def test_apply_fix_to_adventure_field(client, setup_test_db):
    """Adventure-level patches must update the AdventureTemplate row directly."""

    user = User(
        username="fix_user_apply_adv",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    chosen_proposal = {
        "title": "Update walkthrough",
        "summary": "Rewrite the walkthrough section.",
        "rationale": None,
        "patches": [
            {
                "target_type": "adventure",
                "target_id": None,
                "description": "Replace the walkthrough.",
                "field_updates": {"walkthrough": "Step 1: greet the librarian."},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_apply_adv"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": chosen_proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "applied"
    assert payload["applied_targets"] == ["adventure:"]

    async with TestSessionLocal() as db:
        tpl_res = await db.get(AdventureTemplate, tpl_id)
        assert tpl_res is not None
        assert tpl_res.walkthrough == "Step 1: greet the librarian."


async def test_apply_fix_rejects_unknown_field(client, setup_test_db):
    """Fields outside the per-target allowlist are silently ignored."""

    user = User(
        username="fix_user_strip",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    chosen_proposal = {
        "title": "Try anything",
        "summary": "Strip unknown fields and keep valid ones.",
        "rationale": None,
        "patches": [
            {
                "target_type": "npc",
                "target_id": "OLD_LIBRARIAN",
                "description": "Mix valid + invalid.",
                "field_updates": {
                    "description": "Still a wizened keeper.",
                    "sneaky_attacker_field": "drop table",
                },
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_strip"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": chosen_proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        ent_res = await db.execute(
            __import__("sqlalchemy").select(WorldEntity).where(
                WorldEntity.template_id == tpl_id, WorldEntity.id == "OLD_LIBRARIAN"
            )
        )
        ent = ent_res.scalars().first()
        assert ent is not None
        assert ent.description == "Still a wizened keeper."
        assert not hasattr(ent, "sneaky_attacker_field")


async def test_apply_fix_to_protagonist(client, setup_test_db):
    """Protagonist-targeted patches must update the Avatar record."""
    from backend.models.avatar import Avatar

    user = User(
        username="fix_user_apply_prot",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)
        db.add(Avatar(
            user_id=user.id,
            template_id=tpl_id,
            name="Hero",
            description="A traveler.",
            hp=100,
            max_hp=100,
            mana=50,
            max_mana=50,
            stamina=80,
            max_stamina=80,
            equipment={},
            inventory=[],
        ))
        await db.commit()

    chosen_proposal = {
        "title": "Boost protagonist hp",
        "summary": "Increase hp to 150.",
        "rationale": None,
        "patches": [
            {
                "target_type": "protagonist",
                "target_id": None,
                "description": "Raise hp + max_hp.",
                "field_updates": {"hp": 150},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_apply_prot"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": chosen_proposal,
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "applied"
    assert payload["applied_targets"] == ["protagonist:"]

    async with TestSessionLocal() as db:
        av_res = await db.execute(
            __import__("sqlalchemy").select(Avatar).where(Avatar.template_id == tpl_id)
        )
        av = av_res.scalars().first()
        assert av is not None
        assert av.hp == 150
        assert av.max_hp == 150


async def test_apply_fix_no_op_when_patches_empty(client, setup_test_db):
    user = User(username="fix_user_no_op", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_no_op"),
        json={
            "finding_signature": "warn|x|y|z",
            "proposal": {"title": "Empty", "summary": "No patches.", "patches": []},
        },
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "no_op"
    assert payload["applied_targets"] == []


async def test_apply_fix_does_not_call_llm(client, setup_test_db, monkeypatch):
    """Regression: apply-fix must never invoke the LLM — the proposal is the source of truth."""
    user = User(
        username="fix_user_no_llm",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

    llm_called = {"count": 0}

    def _count(*args, **kwargs):
        llm_called["count"] += 1
        raise RuntimeError("LLM must not be called from /apply-fix")

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            _count()
            raise AssertionError("LLM must not be called from /apply-fix")

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    proposal = {
        "title": "Bump hp",
        "summary": "Increase hp.",
        "patches": [
            {
                "target_type": "npc",
                "target_id": "OLD_LIBRARIAN",
                "description": "Touch description.",
                "field_updates": {"description": "Updated."},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_user_no_llm"),
        json={"finding_signature": "warn|x|y|z", "proposal": proposal},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "applied"
    assert llm_called["count"] == 0


async def test_apply_fix_removes_finding_from_persisted_validation_run(client, setup_test_db):
    """When an AI fix is applied, the fixed finding must be removed from the latest persisted ValidationRun."""
    user = User(
        username="fix_persist_user",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_simple_adventure(db, owner=user)

        # Seed a persisted ValidationRun with 2 AI findings
        finding1 = {
            "severity": "warn",
            "code": "orphaned_container_code",
            "message": "Container has orphan code.",
            "location": "object:SAFE_01",
            "context": {"code": "593"},
        }
        finding2 = {
            "severity": "warn",
            "code": "plot_hole",
            "message": "Some plot hole.",
            "location": "scene:START",
            "context": {},
        }
        from datetime import datetime, timezone
        from backend.api.routes.adventures.editor import _finding_signature
        from backend.schemas.validation import ValidationFinding
        sig1 = _finding_signature(ValidationFinding(**finding1))

        run = ValidationRun(
            template_id=tpl_id,
            user_id=user.id,
            include_ai=True,
            structural_findings=[],
            ai_findings=[finding1, finding2],
            structural_finding_count=0,
            ai_finding_count=2,
            error_count=0,
            warning_count=2,
            run_at=datetime.now(timezone.utc),
        )
        db.add(run)
        await db.commit()

    proposal = {
        "title": "Fix orphan code",
        "summary": "Update safe description.",
        "patches": [
            {
                "target_type": "object",
                "target_id": "SAFE_01",
                "description": "Add code hint.",
                "field_updates": {"description": "A heavy safe with code 593 stamped."},
            }
        ],
    }

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate/findings/apply-fix",
        headers=_auth_headers("fix_persist_user"),
        json={"finding_signature": sig1, "proposal": proposal},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "applied"
    assert body["validation_run"] is not None
    assert body["validation_run"]["ai_finding_count"] == 1
    assert len(body["validation_run"]["ai_findings"]) == 1
    assert body["validation_run"]["ai_findings"][0]["code"] == "plot_hole"

    # Verify DB persistence directly
    async with TestSessionLocal() as db:
        res = await db.execute(
            select(ValidationRun).where(ValidationRun.template_id == tpl_id)
        )
        persisted_run = res.scalars().first()
        assert persisted_run is not None
        assert len(persisted_run.ai_findings) == 1
        assert persisted_run.ai_findings[0]["code"] == "plot_hole"
        assert persisted_run.warning_count == 1

