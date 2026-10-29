"""remove the legacy adventure-wide walkthrough

The single global walkthrough was replaced by per-sequence mini-walkthroughs.
Templates that still have a global walkthrough but no sequences are converted
into one 'Main Journey' sequence before the columns are dropped.

Revision ID: d3f8a1b6c2e4
Revises: b4e7a2c9d1f3
Create Date: 2026-10-22 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3f8a1b6c2e4"
down_revision = "b4e7a2c9d1f3"
branch_labels = None
depends_on = None

_templates = sa.table(
    "adventure_templates",
    sa.column("id", sa.String),
    sa.column("walkthrough", sa.String),
    sa.column("plot", sa.String),
    sa.column("completed_condition", sa.String),
    sa.column("sequences", sa.JSON),
)


def _legacy_sequence(walkthrough: str, plot, completed_condition) -> dict:
    # Same shape as backend.engine.rules.sequence_walkthrough.legacy_main_sequence (kept inline
    # so the migration does not depend on application code).
    return {
        "id": "SEQ_1_MAIN",
        "order": 1,
        "title": "Main Journey",
        "description": plot or "Follow the adventure storyline.",
        "walkthrough": walkthrough,
        "end_condition": completed_condition or "Achieve the victory condition.",
        "exp_reward": 500,
    }


def _convert_legacy_walkthroughs() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            _templates.c.id,
            _templates.c.walkthrough,
            _templates.c.plot,
            _templates.c.completed_condition,
            _templates.c.sequences,
        ).where(_templates.c.walkthrough.isnot(None))
    ).fetchall()
    for row in rows:
        walkthrough = (row.walkthrough or "").strip()
        if not walkthrough or row.sequences:
            continue
        bind.execute(
            _templates.update()
            .where(_templates.c.id == row.id)
            .values(sequences=[_legacy_sequence(walkthrough, row.plot, row.completed_condition)])
        )


def upgrade() -> None:
    _convert_legacy_walkthroughs()
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.drop_column("walkthrough")
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.drop_column("walkthrough")


def downgrade() -> None:
    # Converted sequences are kept; the restored columns start empty.
    with op.batch_alter_table("session_states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("walkthrough", sa.String(length=20000), nullable=True))
    with op.batch_alter_table("adventure_templates", schema=None) as batch_op:
        batch_op.add_column(sa.Column("walkthrough", sa.String(length=20000), nullable=True))
