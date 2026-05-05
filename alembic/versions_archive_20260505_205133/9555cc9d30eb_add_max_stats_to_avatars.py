"""Add max_stats to avatars

Revision ID: 9555cc9d30eb
Revises: 352faf1ab337
Create Date: 2026-04-29 07:46:44.319880
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9555cc9d30eb'
down_revision: Union[str, Sequence[str], None] = '352faf1ab337'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Handle Avatar columns
    with op.batch_alter_table('avatars', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_hp', sa.Integer(), server_default='200', nullable=False))
        batch_op.add_column(sa.Column('max_stamina', sa.Integer(), server_default='200', nullable=False))
        batch_op.add_column(sa.Column('max_mana', sa.Integer(), server_default='200', nullable=False))
        # Remove adventure_id if it exists (it seems to be a leftover)
        # batch_op.drop_column('adventure_id') 
        # Actually, let's not drop columns in batch mode if we can avoid it to prevent constraint issues

    # Handle WorldEntity columns
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_hp', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_mana', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('max_stamina', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_strength', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_dexterity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_intelligence', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_wisdom', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_charisma', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('stat_modifier_armor_class', sa.Integer(), nullable=True))

def downgrade() -> None:
    with op.batch_alter_table('world_entities', schema=None) as batch_op:
        batch_op.drop_column('stat_modifier_armor_class')
        batch_op.drop_column('stat_modifier_charisma')
        batch_op.drop_column('stat_modifier_wisdom')
        batch_op.drop_column('stat_modifier_intelligence')
        batch_op.drop_column('stat_modifier_dexterity')
        batch_op.drop_column('stat_modifier_strength')
        batch_op.drop_column('max_stamina')
        batch_op.drop_column('max_mana')
        batch_op.drop_column('max_hp')

    with op.batch_alter_table('avatars', schema=None) as batch_op:
        batch_op.drop_column('max_mana')
        batch_op.drop_column('max_stamina')
        batch_op.drop_column('max_hp')
