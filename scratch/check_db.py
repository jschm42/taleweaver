import sqlite3

conn = sqlite3.connect('data/taleweaver.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

cursor.execute("PRAGMA table_info(users);")
columns = cursor.fetchall()
print("Columns in users:", [c[1] for c in columns])

cursor.execute("PRAGMA table_info(avatars);")
columns = cursor.fetchall()
print("Columns in avatars:", [c[1] for c in columns])

conn.close()
