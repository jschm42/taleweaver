import sqlite3
import os
db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
print("--- adventure_templates ---")
cursor.execute("PRAGMA table_info(adventure_templates);")
for row in cursor.fetchall(): print(row)
print("--- session_states ---")
cursor.execute("PRAGMA table_info(session_states);")
for row in cursor.fetchall(): print(row)
conn.close()
