"""clear the image of CONSTRUCTABLE recipes

Recipes never appear in the world, but older world generation gave them a placeholder image,
which then ended up in every .adz export. The files stay on disk; only the references go.

Revision ID: b8d4f0a2c3e5
Revises: a7c3e9f1b2d4
Create Date: 2026-11-01 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d4f0a2c3e5"
down_revision: Union[str, Sequence[str], None] = "a7c3e9f1b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE world_entities SET image_url = NULL "
            "WHERE upper(item_type) = 'CONSTRUCTABLE' AND image_url IS NOT NULL"
        )
    )


def downgrade() -> None:
    # The placeholder references are not restored: recipes never show an image.
    pass
