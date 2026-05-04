import sqlite3
import json

conn = sqlite3.connect("data/taleweaver.db")
cursor = conn.cursor()

cursor.execute("SELECT title, selected_tone, selected_image_styles FROM adventure_templates")
rows = cursor.fetchall()

for title, tone, styles in rows:
    try:
        if tone: json.loads(tone)
        if styles: json.loads(styles)
    except Exception as e:
        print(f"INVALID DATA for '{title}': Tone={tone}, Styles={styles}, Error={e}")

conn.close()
