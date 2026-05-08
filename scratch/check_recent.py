import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
r = conn.execute("SELECT id, title, creation_status, creation_error, is_ready FROM adventure_templates ORDER BY created_at DESC LIMIT 5").fetchall()
for row in r:
    print(f"ID: {row[0]} | Title: {row[1]} | Status: {row[2]} | Error: {row[3][:50] if row[3] else 'None'}... | Is Ready: {row[4]}")
conn.close()
