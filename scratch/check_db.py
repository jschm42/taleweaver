import sqlite3

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def get_columns(table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

tables = ["adventure_templates", "session_states", "world_entities", "world_exits", "world_scenes"]
for table in tables:
    print(f"Columns in {table}: {get_columns(table)}")

conn.close()
