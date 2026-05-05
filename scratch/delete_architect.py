import sqlite3
import os

db_path = 'data/taleweaver.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM adventure_templates WHERE id = 'the-architect-fgztycua'")
    print(f"Deleted {cursor.rowcount} rows.")
    conn.commit()
    conn.close()
else:
    print("DB not found.")
