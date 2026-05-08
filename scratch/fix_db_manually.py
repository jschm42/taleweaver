import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        print("Adding is_attackable column to world_entities...")
        # SQLite doesn't support IF NOT EXISTS for ADD COLUMN in older versions, 
        # but we can check if it exists first
        cursor.execute("PRAGMA table_info(world_entities)")
        columns = [row[1] for row in cursor.fetchall()]
        if "is_attackable" not in columns:
            cursor.execute("ALTER TABLE world_entities ADD COLUMN is_attackable BOOLEAN NOT NULL DEFAULT 1")
            print("Column added.")
        else:
            print("Column already exists.")
            
        # Ensure we are at the right version
        # Since we fixed the chain, dab2beb3a37f is the head and it includes c75ba74ff965 as parent.
        # The DB already has dab2beb3a37f, so Alembic is happy.
        
        conn.commit()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
else:
    print("Database not found.")
