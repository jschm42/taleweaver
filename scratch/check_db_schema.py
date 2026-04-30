import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for table in ["world_entities", "world_scenes", "world_exits"]:
        print(f"--- Schema for {table} ---")
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        for col in cols:
            print(col)
    conn.close()
else:
    print("DB not found")
