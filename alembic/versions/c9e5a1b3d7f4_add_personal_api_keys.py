"""add personal API keys and the key policy

``server_settings.api_key_policy`` decides per provider who pays (server key, optional or
required personal key, disabled). Players store their own keys in ``users.personal_api_keys``;
admins can override the policy per user in ``users.api_key_policy_overrides``.

Revision ID: c9e5a1b3d7f4
Revises: b8d4f0a2c6e1
Create Date: 2026-11-06 16:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e5a1b3d7f4"
down_revision = "b8d4f0a2c6e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("api_key_policy", sa.JSON(), nullable=True))
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("personal_api_keys", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("api_key_policy_overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("api_key_policy_overrides")
        batch_op.drop_column("personal_api_keys")
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.drop_column("api_key_policy")
