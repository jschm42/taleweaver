import sqlite3
import os

db_path = r'c:\Users\jschmitz\DEV\git-repositories\taleweaver\data\taleweaver.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("UPDATE alembic_version SET version_num = '0b669575012e';")
    if cursor.rowcount == 0:
        cursor.execute("INSERT INTO alembic_version (version_num) VALUES ('0b669575012e');")
    conn.commit()
    print("Successfully updated alembic_version to 0b669575012e")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
