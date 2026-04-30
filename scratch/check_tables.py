import sqlite3

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print([row[0] for row in cursor.fetchall()])

conn.close()
