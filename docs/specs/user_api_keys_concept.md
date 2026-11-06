# Concept: Server Keys vs. Personal API Keys (Bring Your Own Key)

Status: **draft, not implemented**. Builds on the server-wide settings model in
`backend/core/global_settings.py` (single-row table `server_settings`, live overlay onto
every loaded user).

## 1. Goal

The admin decides, per provider, who pays for it:

* **Server keys**: the server's key (env or the key stored in `server_settings`) is used for everyone. This is today's behavior.
* **Personal keys**: a player enters their own key in the profile and pays for their own usage.

A player can thus optionally carry their own costs, and the admin can also make a provider
available only to players who bring a key.

## 2. Key Policy

Every provider that needs a key (`LLM_PROVIDERS`, `IMAGE_PROVIDERS`, TTS: `google`,
`elevenlabs`, STT) gets one policy:

| Policy | Player may enter a key | Key used for the player | No personal key |
| --- | --- | --- | --- |
| `server` (default) | no | server key | server key |
| `user_optional` | yes | personal key, else server key | server key |
| `user_required` | yes, must | personal key | provider unavailable |
| `disabled` | no | none | provider unavailable |

Local providers without a key (`ollama`, `stable_diffusion`, ComfyUI) are always `server`.

### Per-user override

The admin can set a different policy for single users in the user management, e.g.
`user_required` as the default and `server` for family members. Resolution order:
user override → provider policy → `server`.

## 3. Data Model

| Where | Field | Content |
| --- | --- | --- |
| `server_settings` | `api_key_policy` (JSON, new column) | `{"<provider>": "server" \| "user_optional" \| "user_required" \| "disabled"}` |
| Every user | `personal_api_keys` (JSON, new) | `{"<provider>": "<encrypted key>"}` (`encryption_util`, same as server keys) |
| Every user | `api_key_policy_overrides` (JSON, new, admin-writable only) | same shape as `api_key_policy` |

`personal_api_keys` is a **real column** on `users`, unlike the runtime attribute
`User.encrypted_api_keys`, which the overlay fills with the effective keys. The server keys stay
in `server_settings.encrypted_api_keys`, so the two never mix and a player can never overwrite a
server key. One Alembic migration adds the three columns (no data migration).

## 4. Resolution at Runtime

All of it happens in **one place**, `apply_global_settings`, which already builds the
effective settings of a user:

```text
effective_keys = {}
for provider in providers:
    policy = overrides.get(provider) or server_policy.get(provider) or "server"
    personal = user.personal_api_keys.get(provider)
    if policy == "disabled":                  -> skip
    if policy in (user_optional, user_required) and personal:
        effective_keys[provider] = personal  ; source = "personal"
    elif policy == "user_required":           -> skip ; source = "missing"
    else:
        effective_keys[provider] = server key ; source = "server"
user.encrypted_api_keys = effective_keys    # runtime attribute, never persisted
user.key_sources = {provider: source}       # new runtime attribute
```

So `LLMRouter`, `MediaEngine`, the world generator, etc. keep reading `user.encrypted_api_keys`
without changes. Only two places need adjusting:

1. **Env precedence** (`LLMRouter._get_api_key`, `users_api._resolve_provider_api_key`,
   `config_api._resolve_provider_api_key`, `voice_casting.provider_api_key`): today an env key
   always wins. An env key counts as a *server* key: when the source is `personal`, the personal
   key is used, and when the source is `missing` / `disabled`, the env key must **not** be used.
   A shared helper `resolve_api_key(user, provider)` replaces the four copies.
2. **Direct server reads**: these places read the keys from `server_settings` instead of the
   player and must use the player's effective keys: `tts_api._resolve_tts_config` and
   `voice_casting.resolve_voice_setup` / `provider_api_key`. Model lists and profile images
   already read `current_user`, so they pick up personal keys automatically.

Model selection stays server-wide (`llm_settings`). The admin only picks providers whose policy
fits the audience. A "player picks own models when using an own key" option is out of scope
(see §8).

## 5. Error Handling

* A pass whose provider resolves to `missing` raises a typed `PersonalKeyRequired(provider)`
  instead of `ValueError("No API key configured")`. The chat answers it with a clear system
  message ("This server requires your own Anthropic key — add it in Profile → API keys") and
  makes **no** state change (fail-safe, see gameplay guardrails).
* `GET /api/settings` (`is_llm_configured`, `is_t2i_configured`) evaluates the **effective**
  keys of the caller, so the setup wizard and the start screen show the player what is missing.
* An invalid personal key (401 from the provider) is reported as "your key was rejected", never
  falls back to the server key silently.

## 6. API

Player (own row only, `get_current_user`):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/users/me/api-keys` | Per provider: policy, `has_personal_key`, effective source. Keys are never returned. |
| `PUT` | `/api/users/me/api-keys/{provider}` | Store a personal key (only when the policy allows it). The key is test-called first (reuse `test-llm` / `test-vision` / `test-tts` probes). |
| `DELETE` | `/api/users/me/api-keys/{provider}` | Remove a personal key. |

Admin (`get_current_admin`):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`/`PUT` | `/api/settings/key-policy` | Server-wide policy per provider. |
| `PUT` | `/api/users/{id}/key-policy` | Per-user overrides. |
| `GET` | `/api/users` | Additionally `personal_key_providers: [...]` (names only, never values). |

Both new user endpoints go into `tests/test_session_ownership.py`-style checks (a player can
only touch their own keys).

## 7. UI

* **Admin settings → API keys**: one policy dropdown per provider next to the server key field.
  Hint text when `user_required` is set for a provider used by a configured pass.
* **User management**: column "Pays for" with the per-user override.
* **Profile → API keys** (new section, only visible when at least one provider allows personal
  keys): one row per allowed provider with status (`server-paid` / `own key` / `key required`),
  masked input, "Test & save", "Remove".
* **Setup wizard**: for players, a step "Your API keys" when a required key is missing.

## 8. Cost Transparency & Limits

* Telemetry: add `key_source` (`server` / `personal`) to `gm.turn.pipeline.tokens` and the
  image/TTS events, so the admin sees which usage the server pays for.
* Phase 3 (optional): a monthly token/image budget per user for server-paid usage; when it is
  used up, the provider behaves like `user_required` for that user.
* Out of scope: player-selected models with personal keys, payment integration.

## 9. Security

* Personal keys are encrypted like server keys, never returned by any endpoint (only
  `has_personal_key`), never logged, never part of adventure/session export.
* The admin cannot read personal keys, only see which providers have one.
* Deleting a user deletes the keys with the row. Changing the password does not touch them.
* The overlay keeps personal keys of player A out of every other user's instance; a test must
  assert that `apply_global_settings` for player B never contains A's key.

## 10. Implementation Phases

1. Columns + migration, policy resolution in `apply_global_settings`, shared `resolve_api_key`,
   direct server reads switched to effective keys, `PersonalKeyRequired` handling. Tests: policy
   table (§2), env precedence, key isolation between users.
2. Player and admin endpoints, profile section, admin policy UI, setup wizard step, docs.
3. Telemetry `key_source`, optional budgets.
