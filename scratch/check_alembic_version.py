import sqlite3
import os

db_path = "data/taleweaver.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version_num FROM alembic_version")
        rows = cursor.fetchall()
        print("Alembic Versions in DB:")
        for row in rows:
            print(row[0])
    except Exception as e:
        print(f"Error: {e}")
    conn.close()
else:
    print("Database not found.")
