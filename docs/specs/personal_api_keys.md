# Server Keys vs. Personal API Keys (Bring Your Own Key)

The admin decides per provider who pays for it: the server (server key) or the player (the
player's own key). This lets players optionally carry their own costs, and lets the admin offer
a provider only to players who bring a key.

Code: `backend/core/api_keys.py` (policy and key resolution), `backend/core/global_settings.py`
(overlay), `backend/api/routes/api_keys_api.py` (endpoints), `backend/core/turn_key_preflight.py`
(chat check).

## 1. Key Policy

Every provider that takes a key (`api_keys.key_providers()`: the LLM, image and TTS providers
except the local ones) has one policy:

| Policy | Player may store a key | Key used for the player | Without a personal key |
| --- | --- | --- | --- |
| `server` (default) | no | server key | server key |
| `user_optional` | yes | personal key, else server key | server key |
| `user_required` | yes | personal key | provider unavailable |
| `disabled` | no | none | provider unavailable |

Local providers (`ollama`, `stable_diffusion`, `comfyui`, `qwen`) never need a key and are
always `server`.

**Per-user override**: the admin can give single users a different policy (e.g. `user_required`
for everyone, `server` for family members). Resolution order: user override → server policy →
`server`.

## 2. Data Model

| Where | Field | Content |
| --- | --- | --- |
| `server_settings` | `api_key_policy` | `{provider: policy}`; providers left out use `server` |
| `users` | `personal_api_keys` | `{provider: ciphertext}` (Fernet, like the server keys) |
| `users` | `api_key_policy_overrides` | same shape as `api_key_policy`; may say `server` explicitly |

Server keys stay in `server_settings.encrypted_api_keys`. The runtime attribute
`User.encrypted_api_keys` holds the **effective** keys (see §3), so the two never mix and a
player can never overwrite a server key.

## 3. Resolution at Runtime

`apply_global_settings` (called by `get_current_user` and the background loaders) builds the
effective keys with `build_effective_keys(server_keys, server_policy, personal_keys, overrides)`.
The result is an `EffectiveKeys` dict that also records the source of every provider
(`sources`: `server`, `personal`, `missing`, `disabled`).

All code resolves keys through `resolve_api_key(keys, provider)`:

* `personal`: the decrypted personal key. An env key never replaces it.
* `server`: the env key if set, else the stored server key (the previous behavior).
* `missing` / `disabled`: raises `PersonalKeyRequiredError`. The env key is **not** used.

Plain dicts (the server row, tests) have no `sources` and behave like `server`. The image
pipeline copies key dicts with `copy.copy` (`manifest_apply/visuals.t2i_config`), which keeps
`sources`; `dict(...)` would drop them.

Model selection stays server-wide (`llm_settings`): the admin picks providers whose policy
fits the audience. Admins are resolved like every other user, so an admin testing a provider
in the settings uses their own effective key.

## 4. Error Handling

* **Before a chat turn**, `ensure_turn_providers_available` checks the providers of the
  mechanics and narration passes. A blocked provider answers `POST /chat` with HTTP 403 and
  `detail = {code: "personal_key_required", provider, reason, message}` before anything is
  stored, so the turn has no side effects. The chat shows `message` as a system message.
* **During a turn** (e.g. a compression or script model), `PersonalKeyRequiredError` is turned
  into the same user-facing message by `_friendly_llm_error_message`.
* **Portal**: `GET /api/settings` returns `missing_personal_keys` (blocked chat passes) and
  evaluates `is_llm_configured` / `is_t2i_configured` with the caller's effective keys. The
  portal banner tells the player which key to add.
* TTS answers HTTP 403 with the message; image generation fails with it.
* There is no silent fallback: a rejected personal key (HTTP 401 from the provider) is
  reported as an authentication error, never retried with the server key.

## 5. API

Player (own row only):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/users/me/api-keys` | Per provider: `policy`, `can_store_key`, `has_personal_key`, effective `source`. Keys are never returned. |
| `PUT` | `/api/users/me/api-keys/{provider}` | Body `{api_key}`. Only when the policy allows personal keys (else 403). The key is checked with a free model-list call where the provider has one (`model_discovery.verify_api_key`); a rejected key is not stored (400). The response says `verified`. |
| `DELETE` | `/api/users/me/api-keys/{provider}` | Remove the personal key. |

Admin:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` / `PUT` | `/api/settings/key-policy` | Server-wide policy, body `{policy: {provider: policy}}`. Unknown providers or policies answer 422. |
| `PUT` | `/api/users/{id}/key-policy` | Per-user overrides, same body. |
| `GET` | `/api/users` | Each user additionally has `personal_key_providers` (names only) and `api_key_policy_overrides`. |

## 6. UI

* **Administration → Provider Vault**: a "Who pays" select per provider (saved immediately).
* **Administration → User Management**: column "Own keys" (providers with a personal key,
  number of exceptions); the user dialog has a "Who pays for this user" editor.
* **Profile → Account → API keys**: shown when at least one provider allows personal keys;
  status per provider (server pays / own key / key required), "Test & save", "Remove".
* **Portal banner**: "Your own API key is needed" while a chat pass is blocked.

## 7. Telemetry

`gm.turn.pipeline.tokens` carries `key_source` (`server` / `personal`) for the narration, so
the admin can see which usage the server pays for.

## 8. Security

* Personal keys are encrypted at rest, never returned by any endpoint, never logged, and not
  part of adventure or session exports.
* Admins see only which providers have a personal key, never the key.
* Deleting a user deletes the keys with the row. Changing the password does not touch them.
* Every user gets their own `EffectiveKeys`; tests assert that a player's personal key never
  appears in another user's keys (`tests/test_personal_api_keys.py`).

## 9. Not Implemented (Possible Follow-ups)

* Monthly budgets for server-paid usage per user.
* `key_source` on image and TTS telemetry events.
* Player-selected models when using an own key.
* A dedicated setup-wizard step for players; the portal banner covers the missing-key case.
