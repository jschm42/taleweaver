import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", tables)
cursor.execute("SELECT * FROM alembic_version")
print("Alembic Version:", cursor.fetchone())
conn.close()
