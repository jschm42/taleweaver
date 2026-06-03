import sqlite3
db_path = r"d:\DEV\repositories\git\taleweaver\data\taleweaver.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT id, username, role FROM users")
print("Users:", cur.fetchall())

cur.execute("SELECT id, title FROM adventure_templates")
print("Templates:", cur.fetchall())

conn.close()
