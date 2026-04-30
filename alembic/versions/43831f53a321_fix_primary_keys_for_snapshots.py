"""fix_primary_keys_for_snapshots

Revision ID: 43831f53a321
Revises: 6dc8e0811c64
Create Date: 2026-04-30 10:03:16.266551
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '43831f53a321'
down_revision: Union[str, Sequence[str], None] = '6dc8e0811c64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix world_entities
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        # We need to recreate the table with pk as the primary key.
        # SQLite batch_op handles this by creating a new table and copying data.
        # However, we must ensure pk is correctly defined.
        batch_op.alter_column('pk',
               existing_type=sa.Integer(),
               type_=sa.Integer(),
               primary_key=True,
               autoincrement=True,
               nullable=False)
        # We also need to remove the primary key constraint from 'id'
        # batch_op handles this if we specify the new primary key.
    
    # Fix world_scenes
    with op.batch_alter_table('world_scenes', schema=None) as batch_op:
        batch_op.alter_column('pk',
               existing_type=sa.Integer(),
               type_=sa.Integer(),
               primary_key=True,
               autoincrement=True,
               nullable=False)

def downgrade() -> None:
    # Revert world_entities
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        batch_op.alter_column('pk',
               existing_type=sa.Integer(),
               type_=sa.Integer(),
               primary_key=False,
               nullable=True)
        # Note: Reverting back to 'id' as PK is complex in batch mode without explicit PK definition.
        # This downgrade is simplified and might not fully restore the exact PK structure.
    
    # Revert world_scenes
    with op.batch_alter_table('world_scenes', schema=None) as batch_op:
        batch_op.alter_column('pk',
               existing_type=sa.Integer(),
               type_=sa.Integer(),
               primary_key=False,
               nullable=True)
