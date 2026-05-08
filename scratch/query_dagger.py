import sqlite3
import os

db_path = "data/taleweaver.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT id, name, entity_type, image_url FROM world_entities WHERE name LIKE '%Rusty Dagger%';")
rows = cursor.fetchall()
for row in rows:
    print(row)
conn.close()
