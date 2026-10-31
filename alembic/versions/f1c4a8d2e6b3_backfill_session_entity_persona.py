"""backfill persona, voice and reveal fields of session entities from their template

Session copies of world entities used to be created without ``appearance``, ``voice``,
``goal``, ``character`` and ``reveal_rule``. Running games therefore lost NPC voices and
personas. Fill the missing (NULL) values from the template entity with the same ID; values a
game already has are kept (script persona changes live in ``entity_states``, not here).

Revision ID: f1c4a8d2e6b3
Revises: e5b9d3f7a2c4
Create Date: 2026-10-31 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1c4a8d2e6b3"
down_revision: Union[str, Sequence[str], None] = "e5b9d3f7a2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIELDS = ("appearance", "voice", "goal", "character", "reveal_rule")


def upgrade() -> None:
    columns = [sa.column(field) for field in _FIELDS]
    entities = sa.table(
        "world_entities",
        sa.column("id"),
        sa.column("session_id"),
        sa.column("template_id"),
        *columns,
    )
    states = sa.table("session_states", sa.column("session_id"), sa.column("template_id"))
    template = entities.alias("tmpl")
    for field in _FIELDS:
        template_value = (
            sa.select(template.c[field])
            .select_from(template.join(states, states.c.template_id == template.c.template_id))
            .where(
                states.c.session_id == entities.c.session_id,
                template.c.session_id.is_(None),
                template.c.id == entities.c.id,
            )
            .limit(1)
            .scalar_subquery()
        )
        op.execute(
            sa.update(entities)
            .where(entities.c.session_id.is_not(None), entities.c[field].is_(None))
            .values({field: template_value})
        )


def downgrade() -> None:
    # Data backfill only: the previous NULLs carried no information worth restoring.
    pass
