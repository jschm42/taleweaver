import sqlite3
from backend.core.auth import get_password_hash

db_path = r"d:\DEV\repositories\git\taleweaver\data\taleweaver.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

new_hash = get_password_hash("admin")
cur.execute("UPDATE users SET hashed_password = ? WHERE username = 'admin'", (new_hash,))
conn.commit()
print("Updated admin password to 'admin'")

conn.close()
