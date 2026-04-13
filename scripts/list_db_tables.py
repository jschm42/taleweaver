import sqlite3
import os

DB_PATH = "backend/taleweaver.db"

def list_tables():
    if not os.path.exists(DB_PATH):
        print(f"No database found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in DB:", [t[0] for t in tables])
    conn.close()

if __name__ == "__main__":
    list_tables()
