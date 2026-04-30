import sqlite3

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '_alembic_tmp_%';")
tables = [row[0] for row in cursor.fetchall()]
for table in tables:
    try:
        cursor.execute(f"DROP TABLE {table}")
        print(f"Dropped {table}")
    except Exception as e:
        print(f"Error dropping {table}: {e}")

conn.commit()
conn.close()
