"""Update selected_tone and selected_image_styles to JSON objects

Revision ID: aa67131aff30
Revises: df909b39afb3
Create Date: 2026-05-04 18:58:14.447069
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite


# revision identifiers, used by Alembic.
revision: str = 'aa67131aff30'
down_revision: Union[str, Sequence[str], None] = 'df909b39afb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
import json

# default catalog fallback for data migration
DEFAULT_STYLES = [
    {"id": "dark-fantasy-painting", "name": "Dark Fantasy Painting", "description": "Moody brushwork with dramatic contrast and medieval grit.", "instruction": "dark fantasy painting, dramatic chiaroscuro, textured brush strokes, rich atmosphere"},
    {"id": "cinematic-realism", "name": "Cinematic Realism", "description": "Film-like composition with realistic lighting and depth.", "instruction": "cinematic realism, volumetric lighting, detailed environment, film still composition"},
    {"id": "stylized-rpg-art", "name": "Stylized RPG Art", "description": "Bold outlines, vivid palettes, and heroic fantasy readability.", "instruction": "stylized RPG concept art, clean silhouettes, vibrant but grounded colors"},
    {"id": "grimdark-ink-sketch", "name": "Grimdark Ink Sketch", "description": "Raw, hand-drawn aesthetic with heavy ink washes and scratched textures.", "instruction": "grimdark ink sketch, cross-hatching, distressed paper texture, high contrast black and white"},
    {"id": "cyberpunk-neon", "name": "Cyberpunk Neon", "description": "Vibrant neon lights, rainy cityscapes, and high-tech grit.", "instruction": "cyberpunk aesthetic, synthwave colors, neon glow, wet asphalt reflections, futuristic noir"},
    {"id": "ethereal-watercolor", "name": "Ethereal Watercolor", "description": "Soft, bleeding colors with a dreamlike, mystical atmosphere.", "instruction": "ethereal watercolor painting, soft edges, bleeding pigments, mystical light, dreamy pastel tones"},
    {"id": "science-fiction", "name": "Science-Fiction", "description": "Futuristic tech, vast space, and advanced starships.", "instruction": "futuristic science fiction world, starships in the sky, sleek high tech architecture, glowing neon lights, cinematic composition"},
    {"id": "pixelart", "name": "Pixelart", "description": "Classic 90s adventure style with vibrant colors and charming pixels.", "instruction": "90s point and click adventure game pixel art, LucasArts style, vibrant limited color palette, pixelated aesthetic"}
]

DEFAULT_TONES = [
    {"id": "horror", "name": "Horror", "description": "Dread, uncertainty, and escalating psychological pressure.", "instruction": "Maintain unsettling tension, sparse comfort, and consequences that feel dangerous."},
    {"id": "sci-fi", "name": "Sci-Fi", "description": "Futuristic systems, unknown tech, and speculative mystery.", "instruction": "Use futuristic world logic, technical flavor, and discovery-driven narrative beats."},
    {"id": "sitcom", "name": "Sitcom", "description": "Comedic misunderstandings, playful pacing, and memorable banter.", "instruction": "Favor witty dialogue, comic timing, and low-stakes chaos with charming setbacks."},
    {"id": "classic-rpg", "name": "Classic RPG", "description": "Heroic quest tone with balanced drama and wonder.", "instruction": "Keep a classic heroic arc, meaningful choices, and clear quest momentum."},
    {"id": "heroic-epic", "name": "Heroic & Epic", "description": "Grand scale, legendary deeds, and inspiring bravery.", "instruction": "The tone is heroic and epic. Focus on grand scale, legendary atmosphere, and inspiring narratives."},
    {"id": "melancholic-somber", "name": "Melancholic & Somber", "description": "Reflective, sad, and focused on loss or faded glory.", "instruction": "The tone is melancholic and somber. Use reflective language, focus on themes of loss and beauty in sadness."},
    {"id": "grimdark-gritty", "name": "Grimdark & Gritty", "description": "Brutal, uncompromising, and focused on survival against all odds.", "instruction": "The tone is grimdark and gritty. Highlight the harshness of the world, moral ambiguity, and the weight of consequences."}
]

def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    # Update adventure_templates
    columns = [c['name'] for c in inspector.get_columns('adventure_templates')]
    with op.batch_alter_table('adventure_templates', schema=None) as batch_op:
        # SQLite doesn't natively support altering column types, but batch_alter_table rebuilds it.
        # We drop and recreate if needed, or just let batch_op handle the type change to JSON.
        batch_op.alter_column('selected_tone',
               existing_type=sa.VARCHAR(length=100),
               type_=sa.JSON(),
               existing_nullable=True)
               
    # Update session_states
    columns_session = [c['name'] for c in inspector.get_columns('session_states')]
    with op.batch_alter_table('session_states', schema=None) as batch_op:
        if 'selected_image_styles' not in columns_session:
            batch_op.add_column(sa.Column('selected_image_styles', sa.JSON(), nullable=True))
        if 'selected_tone' not in columns_session:
            batch_op.add_column(sa.Column('selected_tone', sa.JSON(), nullable=True))
            
    # Data migration for adventure_templates
    res = conn.execute(sa.text("SELECT id, selected_tone, selected_image_styles FROM adventure_templates")).fetchall()
    
    tone_map = {t["id"]: t for t in DEFAULT_TONES}
    style_map = {s["id"]: s for s in DEFAULT_STYLES}
    
    for row in res:
        adv_id, t_val, s_val = row
        new_t_val = None
        new_s_val = None
        
        # Migrate selected_tone
        if t_val:
            try:
                # Might already be JSON
                parsed = json.loads(t_val)
                if isinstance(parsed, str):
                    t_val = parsed # it was a JSON string containing a string
                else:
                    new_t_val = parsed
            except:
                pass
                
            if new_t_val is None and isinstance(t_val, str):
                if t_val in tone_map:
                    new_t_val = tone_map[t_val]
                else:
                    new_t_val = {"id": t_val, "name": t_val, "description": "", "instruction": ""}
        
        # Migrate selected_image_styles
        if s_val:
            try:
                parsed = json.loads(s_val)
                if isinstance(parsed, list):
                    new_list = []
                    for item in parsed:
                        if isinstance(item, str):
                            if item in style_map:
                                new_list.append(style_map[item])
                            else:
                                new_list.append({"id": item, "name": item, "description": "", "instruction": ""})
                        elif isinstance(item, dict):
                            new_list.append(item)
                    new_s_val = new_list
                elif isinstance(parsed, str):
                    if parsed in style_map:
                        new_s_val = [style_map[parsed]]
                    else:
                        new_s_val = [{"id": parsed, "name": parsed, "description": "", "instruction": ""}]
            except:
                pass

        if new_t_val is not None or new_s_val is not None:
            updates = []
            params = {"id": adv_id}
            if new_t_val is not None:
                updates.append("selected_tone = :t")
                params["t"] = json.dumps(new_t_val)
            if new_s_val is not None:
                updates.append("selected_image_styles = :s")
                params["s"] = json.dumps(new_s_val)
                
            if updates:
                stmt = sa.text(f"UPDATE adventure_templates SET {', '.join(updates)} WHERE id = :id")
                conn.execute(stmt, params)

def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    
    columns_session = [c['name'] for c in inspector.get_columns('session_states')]
    with op.batch_alter_table('session_states', schema=None) as batch_op:
        if 'selected_tone' in columns_session:
            batch_op.drop_column('selected_tone')
        if 'selected_image_styles' in columns_session:
            batch_op.drop_column('selected_image_styles')

    with op.batch_alter_table('adventure_templates', schema=None) as batch_op:
        batch_op.alter_column('selected_tone',
               existing_type=sa.JSON(),
               type_=sa.VARCHAR(length=100),
               existing_nullable=True)
