"""add cover metadata to adventure templates

Revision ID: 9c1b7e2d4a11
Revises: f69e714a3585
Create Date: 2026-05-20 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c1b7e2d4a11"
down_revision = "f69e714a3585"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("adventure_templates")}

    if "cover_source_adventure_id" not in existing_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("cover_source_adventure_id", sa.String(length=36), nullable=True),
        )

    if "cover_source_adventure_name" not in existing_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("cover_source_adventure_name", sa.String(length=100), nullable=True),
        )

    if "cover_similarity_percent" not in existing_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("cover_similarity_percent", sa.Integer(), nullable=False, server_default="50"),
        )

    if "allow_reuse_source_assets" not in existing_columns:
        op.add_column(
            "adventure_templates",
            sa.Column("allow_reuse_source_assets", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("adventure_templates")}

    if "allow_reuse_source_assets" in existing_columns:
        op.drop_column("adventure_templates", "allow_reuse_source_assets")
    if "cover_similarity_percent" in existing_columns:
        op.drop_column("adventure_templates", "cover_similarity_percent")
    if "cover_source_adventure_name" in existing_columns:
        op.drop_column("adventure_templates", "cover_source_adventure_name")
    if "cover_source_adventure_id" in existing_columns:
        op.drop_column("adventure_templates", "cover_source_adventure_id")
