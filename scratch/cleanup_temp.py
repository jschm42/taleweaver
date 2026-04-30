import sqlite3

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("DROP TABLE _alembic_tmp_avatars")
    print("Dropped _alembic_tmp_avatars")
except:
    pass

conn.commit()
conn.close()
