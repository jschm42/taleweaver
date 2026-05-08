import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
r = conn.execute('SELECT title, length(original_prompt), length(intro_text) FROM adventure_templates WHERE id="5e687f41-3ae5-403a-81d5-745e778f11fe"').fetchone()
print(f"Title: {r[0]}")
print(f"Original Prompt Length: {r[1]}")
print(f"Intro Text Length: {r[2]}")
conn.close()
