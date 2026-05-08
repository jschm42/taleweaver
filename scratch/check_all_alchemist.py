import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
r = conn.execute("SELECT id, title, creation_status, creation_error, is_ready FROM adventure_templates WHERE title LIKE ?", ('%Alchemist%',)).fetchall()
for row in r:
    print(f"ID: {row[0]} | Title: {row[1]} | Status: {row[2]} | Error: {row[3][:50]}... | Is Ready: {row[4]}")
conn.close()
