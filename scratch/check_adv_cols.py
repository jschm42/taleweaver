import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(adventure_templates)")
    cols = cursor.fetchall()
    print("adventure_templates columns:")
    for c in cols:
        print(f"- {c[1]} ({c[2]})")
    conn.close()
else:
    print("DB not found")
