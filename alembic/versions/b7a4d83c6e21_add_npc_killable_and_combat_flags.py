"""add npc killable and combat flags

Revision ID: b7a4d83c6e21
Revises: 9c1b7e2d4a11
Create Date: 2026-05-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7a4d83c6e21"
down_revision = "9c1b7e2d4a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    template_columns = {col["name"] for col in inspector.get_columns("adventure_templates")}
    entity_columns = {col["name"] for col in inspector.get_columns("world_entities")}

    if "can_damage_npcs" not in template_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("can_damage_npcs", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "npcs_can_damage_protagonist" not in template_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("npcs_can_damage_protagonist", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )

    if "is_killable" not in entity_columns:
        op.add_column(
            "world_entities",
            sa.Column("is_killable", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    template_columns = {col["name"] for col in inspector.get_columns("adventure_templates")}
    entity_columns = {col["name"] for col in inspector.get_columns("world_entities")}

    if "is_killable" in entity_columns:
        op.drop_column("world_entities", "is_killable")

    if "npcs_can_damage_protagonist" in template_columns:
        op.drop_column("adventure_templates", "npcs_can_damage_protagonist")

    if "can_damage_npcs" in template_columns:
        op.drop_column("adventure_templates", "can_damage_npcs")
