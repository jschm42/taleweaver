"""backfill scripts and decorations of session scene copies

Session scene copies used to drop the enter/leave scripts and decorations, so those scripts
never fired in a game. Fills the empty columns from the same scene of the session's template.

Revision ID: a7c3e9f5b2d1
Revises: f2b6d8e4a1c9
Create Date: 2026-10-30 12:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

_BACKFILL_COLUMNS = (
    "decorative_objects",
    "on_enter_scene_script",
    "on_enter_scene_text",
    "on_leave_scene_script",
    "on_leave_scene_text",
    "helpers_script",
)

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f5b2d1"
down_revision: Union[str, Sequence[str], None] = "f2b6d8e4a1c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    scenes = sa.table(
        "world_scenes",
        sa.column("id"),
        sa.column("session_id"),
        sa.column("template_id"),
        *(sa.column(name) for name in _BACKFILL_COLUMNS),
    )
    states = sa.table("session_states", sa.column("session_id"), sa.column("template_id"))
    template = scenes.alias("template_scene")
    for name in _BACKFILL_COLUMNS:
        source = (
            sa.select(template.c[name])
            .select_from(template.join(states, states.c.template_id == template.c.template_id))
            .where(
                states.c.session_id == scenes.c.session_id,
                template.c.id == scenes.c.id,
                template.c.session_id.is_(None),
            )
            .limit(1)
            .scalar_subquery()
        )
        op.execute(
            sa.update(scenes)
            .where(scenes.c.session_id.isnot(None), scenes.c[name].is_(None))
            .values({name: source})
        )


def downgrade() -> None:
    # Data-only migration: the copied scripts are correct data and stay.
    pass
