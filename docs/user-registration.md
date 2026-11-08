# User Accounts: Self-Registration, Approval & First-Login Onboarding

TaleWeaver is single-tenant, but it supports multiple accounts. There are three ways an
account comes into existence:

| Path | Who | Account state |
| --- | --- | --- |
| First-run setup (`POST /api/v1/auth/setup`) | The first administrator | active, `role = "admin"` |
| Admin user management (`POST /api/v1/users`) | Administrators | active unless the admin clears **Account active** |
| Self-registration (`POST /api/v1/auth/register`) | Anyone with access to the login page | **inactive** until an administrator approves it |

## Self-registration

Public page at `/register`, linked from `/login` ("No account yet? Create one"). It asks for
username, e-mail and password (plus a confirmation field). Client-side it enforces matching
passwords and the server's password policy (`GET /api/v1/auth/bootstrap-status` →
`password_policy`), server-side the same rules apply via `validate_username` and
`validate_password_strength`.

```
POST /api/v1/auth/register
{ "username": "ada", "email": "ada@example.com", "password": "..." }
-> 201 { "message": "Registration successful. Your account is pending administrator approval..." }
```

* Usernames and e-mail addresses are unique, compared case-insensitively
  (`backend/api/routes/user_account_checks.py`); duplicates return `400` with a readable detail.
* Registrations are rate limited per IP: 10 attempts per 15 minutes (`register_throttle`),
  then `429`.
* The created row has `is_active = False`. Such an account cannot log in: `POST /api/v1/auth/token`
  answers `403` with `"Account is pending administrator approval."`, and an already issued token
  stops working because `get_current_user` rejects inactive users.
* Self-registration never creates administrators (`role` is always `"user"`).

## Administrator approval

The **Users** panel in the admin area lists every account with its e-mail and a status badge
(`Pending approval` / `Active`). Pending rows offer an **Approve account** action, which calls:

```
POST /api/v1/users/{user_id}/activate   (admin only) -> UserResponse
```

The same effect is available in the edit dialog via the **Account active** checkbox
(`PUT /api/v1/users/{user_id}` with `is_active`). Both routes refuse to deactivate the last
remaining active administrator, so administration can never lock itself out.

Deactivation takes effect immediately: existing sessions are rejected on the next request.

## First-login onboarding wizard

Approval alone does not show anything. The wizard is driven by the per-user setup-wizard state
(`GET/PUT /api/v1/settings/setup-wizard`), which defaults to `pending` and is scoped to the
signed-in account.

* **Regular users** get `UserOnboardingWizard.vue` on their first login after approval:
  welcome → story language (`default_language`) → voice/auto-speak (`tts_preferences.enabled`).
  Finishing stores `state = "completed"`, closing it stores `"skipped"`; either way it does not
  reappear. The settings can be changed later in the profile settings.
* **Administrators** keep the server-wide setup wizard (`SetupWizardModal.vue`) for LLM,
  image and audio configuration.

Because the state lives per user, approving or dismissing the wizard never affects other
accounts. Deleting a user and recreating it therefore shows the wizard again.

## E-mail addresses

E-mail is optional for admin-created accounts and mandatory for self-registration. It is
currently used for identification and admin overview only — TaleWeaver does not send mail.
Password recovery still works through the recovery codes issued in the profile settings.

## Database

`alembic/versions/e8c9d1a2b3f4_add_email_and_is_active_to_users.py` (chained from
`b5e1f8c3a9d2`) adds `users.email` (unique index `ix_users_email`, nullable) and
`users.is_active` (not null, server default `1`, so pre-existing accounts stay active).
