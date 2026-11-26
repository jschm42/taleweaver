"""world map as a grid of image tiles

Revision ID: f1b3d5e7a9c2
Revises: e8a0c2d4f6b7
Create Date: 2026-11-21 18:00:00.000000

Replaces the single world map image with a tile layout
({"cols", "rows", "tiles": [{"col", "row", "url"}]}); an existing image becomes the only tile
of a 1x1 grid. Downgrade keeps the top-left tile as the single image.
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b3d5e7a9c2"
down_revision: Union[str, Sequence[str], None] = "e8a0c2d4f6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEMPLATES = sa.table(
    "adventure_templates",
    sa.column("id", sa.String),
    sa.column("world_map_image_url", sa.String),
    sa.column("world_map_layout", sa.JSON),
)


def upgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_map_layout", sa.JSON(), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(_TEMPLATES.c.id, _TEMPLATES.c.world_map_image_url).where(
            _TEMPLATES.c.world_map_image_url.isnot(None)
        )
    ).all()
    for template_id, url in rows:
        layout = {"cols": 1, "rows": 1, "tiles": [{"col": 0, "row": 0, "url": url}]}
        bind.execute(
            _TEMPLATES.update()
            .where(_TEMPLATES.c.id == template_id)
            .values(world_map_layout=layout)
        )
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_map_image_url")


def downgrade() -> None:
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("world_map_image_url", sa.String(length=255), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(_TEMPLATES.c.id, _TEMPLATES.c.world_map_layout).where(
            _TEMPLATES.c.world_map_layout.isnot(None)
        )
    ).all()
    for template_id, raw in rows:
        layout = json.loads(raw) if isinstance(raw, str) else raw or {}
        first = next(
            (t for t in layout.get("tiles") or [] if t.get("col") == 0 and t.get("row") == 0), None
        )
        if first:
            bind.execute(
                _TEMPLATES.update()
                .where(_TEMPLATES.c.id == template_id)
                .values(world_map_image_url=first.get("url"))
            )
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("world_map_layout")
