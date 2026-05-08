import sqlite3
import os

db_path = "data/taleweaver.db"
new_version = "0b669575012e"

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if alembic_version table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
    if not cursor.fetchone():
        print("Table 'alembic_version' does not exist. Creating it.")
        cursor.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        cursor.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (new_version,))
    else:
        # Get current version
        cursor.execute("SELECT version_num FROM alembic_version")
        row = cursor.fetchone()
        if row:
            print(f"Current version: {row[0]}")
            cursor.execute("UPDATE alembic_version SET version_num = ?", (new_version,))
        else:
            print("No version found in alembic_version table. Inserting new one.")
            cursor.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (new_version,))
    
    conn.commit()
    print(f"Successfully updated alembic_version to {new_version}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
