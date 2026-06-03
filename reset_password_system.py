import sqlite3
db_path = r"d:\DEV\repositories\git\taleweaver\data\taleweaver.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Bcrypt hash for password 'admin'
new_hash = "$2b$12$y17gW2i/MewR1GqyOEvO/Oa/Sihq9oX94uMswzH.jA/8fO6jHlQhS"

cur.execute("UPDATE users SET hashed_password = ? WHERE username = 'admin'", (new_hash,))
conn.commit()
print("Updated admin password in DB")

conn.close()
