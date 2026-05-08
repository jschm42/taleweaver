import sqlite3
import json
import os

db_path = "data/taleweaver.db"
target_id = "5e687f41-3ae5-403a-81d5-745e778f11fe"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM adventure_templates WHERE id = ?", (target_id,))
    row = cursor.fetchone()
    if row:
        print(f"Data for adventure {target_id}:")
        for key in row.keys():
            print(f"- {key}: {row[key]}")
    else:
        print(f"Adventure {target_id} not found.")
    conn.close()
else:
    print("DB not found")
