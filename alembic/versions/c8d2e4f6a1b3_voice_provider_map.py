"""add the per-provider voice mapping of the voice list

``server_settings.voice_provider_map`` stores which Google TTS / OpenAI-compatible voice speaks
each voice of the (ElevenLabs) voice list; see backend/engine/audio/voice_provider_map.py.

Revision ID: c8d2e4f6a1b3
Revises: b5e1f8c3a9d2
Create Date: 2026-11-09 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d2e4f6a1b3"
down_revision = "b5e1f8c3a9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voice_provider_map", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("server_settings", schema=None) as batch_op:
        batch_op.drop_column("voice_provider_map")
