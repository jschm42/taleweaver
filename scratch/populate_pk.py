import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for table in ["world_entities", "world_scenes"]:
        print(f"Populating pk for {table}...")
        # Get all rows
        cursor.execute(f"SELECT rowid FROM {table}")
        rows = cursor.fetchall()
        for idx, (rowid,) in enumerate(rows, 1):
            cursor.execute(f"UPDATE {table} SET pk = ? WHERE rowid = ?", (idx, rowid))
    
    conn.commit()
    conn.close()
    print("Done")
else:
    print("DB not found")
