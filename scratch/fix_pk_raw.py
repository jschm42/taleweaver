import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fix world_entities
    print("Fixing world_entities primary key...")
    # Get original columns (excluding pk which might be there but we want to redefine it)
    cursor.execute("PRAGMA table_info(world_entities)")
    cols = [c[1] for c in cursor.fetchall() if c[1] != 'pk']
    cols_str = ", ".join(cols)
    
    # Create new table
    # We need to look up the full definition, but I can just reconstruct it based on the model
    # To be safe, I'll just use a generic INTEGER PRIMARY KEY AUTOINCREMENT for pk
    # and then the rest of the columns as they are.
    
    # Actually, a better way: rename old, create new, copy data
    cursor.execute("ALTER TABLE world_entities RENAME TO world_entities_old")
    
    # Define new table (based on model)
    # I'll just copy the schema from the old table but change the PK
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='world_entities_old'")
    old_sql = cursor.fetchone()[0]
    # The old SQL has "PRIMARY KEY (id)" or similar.
    # This is hard to regex reliably. 
    # I'll just write the CREATE TABLE manually based on the model learnings.
    
    new_sql = """
    CREATE TABLE world_entities (
        pk INTEGER PRIMARY KEY AUTOINCREMENT,
        id VARCHAR(50) NOT NULL,
        template_id VARCHAR(36),
        session_id VARCHAR(36),
        entity_type VARCHAR(20) NOT NULL,
        name VARCHAR(100) NOT NULL,
        description VARCHAR(1000) NOT NULL,
        current_scene_id VARCHAR(50) NOT NULL,
        spatial_position VARCHAR(255),
        image_url VARCHAR(255),
        item_type VARCHAR(50),
        wearable_slots JSON,
        is_in_inventory BOOLEAN NOT NULL DEFAULT 0,
        is_hidden BOOLEAN NOT NULL DEFAULT 0,
        is_portable BOOLEAN NOT NULL DEFAULT 1,
        combination_ingredients JSON,
        reveals_item_id VARCHAR(50),
        is_final_state BOOLEAN NOT NULL DEFAULT 0,
        state_comment VARCHAR(1000),
        npc_type VARCHAR(50),
        movement_type VARCHAR(50),
        hp INTEGER,
        max_hp INTEGER,
        mana INTEGER,
        max_mana INTEGER,
        stamina INTEGER,
        max_stamina INTEGER,
        stat_modifier_strength INTEGER,
        stat_modifier_dexterity INTEGER,
        stat_modifier_intelligence INTEGER,
        stat_modifier_wisdom INTEGER,
        stat_modifier_charisma INTEGER,
        stat_modifier_armor_class INTEGER,
        inventory JSON NOT NULL DEFAULT '[]',
        metadata_json JSON NOT NULL DEFAULT '{}',
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE,
        FOREIGN KEY(template_id) REFERENCES adventure_templates (id) ON DELETE SET NULL
    )
    """
    cursor.execute(new_sql)
    
    # Copy data (excluding pk, it will autoincrement)
    # We must match the columns carefully.
    cursor.execute(f"INSERT INTO world_entities ({cols_str}) SELECT {cols_str} FROM world_entities_old")
    
    cursor.execute("DROP TABLE world_entities_old")

    # Fix world_scenes
    print("Fixing world_scenes primary key...")
    cursor.execute("PRAGMA table_info(world_scenes)")
    cols = [c[1] for c in cursor.fetchall() if c[1] != 'pk']
    cols_str = ", ".join(cols)
    
    cursor.execute("ALTER TABLE world_scenes RENAME TO world_scenes_old")
    
    new_sql = """
    CREATE TABLE world_scenes (
        pk INTEGER PRIMARY KEY AUTOINCREMENT,
        id VARCHAR(50) NOT NULL,
        template_id VARCHAR(36),
        session_id VARCHAR(36),
        label VARCHAR(100) NOT NULL,
        description VARCHAR(2000) NOT NULL,
        image_url VARCHAR(255),
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES game_sessions (id) ON DELETE CASCADE,
        FOREIGN KEY(template_id) REFERENCES adventure_templates (id) ON DELETE SET NULL
    )
    """
    cursor.execute(new_sql)
    cursor.execute(f"INSERT INTO world_scenes ({cols_str}) SELECT {cols_str} FROM world_scenes_old")
    cursor.execute("DROP TABLE world_scenes_old")
    
    conn.commit()
    conn.close()
    print("Done")
else:
    print("DB not found")
