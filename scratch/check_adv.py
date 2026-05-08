import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
r = conn.execute("SELECT id, title, creation_status, creation_error, is_ready FROM adventure_templates WHERE id = ?", ('69529b8d-2989-4952-a457-ab4f141f3a2b',)).fetchone()
print(f"ID: {r[0]}")
print(f"Title: {r[1]}")
print(f"Status: {r[2]}")
print(f"Error: {r[3]}")
print(f"Is Ready: {r[4]}")
conn.close()
