import sqlite3
import json
import os

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT id, selected_tone, selected_image_styles FROM adventure_templates;")
    rows = cursor.fetchall()
    
    for row_id, tone, styles in rows:
        updated = False
        new_tone = tone
        new_styles = styles
        
        if tone:
            try:
                parsed_tone = json.loads(tone)
                if not isinstance(parsed_tone, dict):
                    new_tone = json.dumps({"id": str(parsed_tone)})
                    updated = True
            except:
                new_tone = json.dumps({"id": tone})
                updated = True

        if styles:
            try:
                parsed_styles = json.loads(styles)
                if isinstance(parsed_styles, list) and len(parsed_styles) > 0 and not isinstance(parsed_styles[0], dict):
                    new_styles = json.dumps([{"id": str(s)} for s in parsed_styles])
                    updated = True
                elif not isinstance(parsed_styles, list):
                    new_styles = json.dumps([{"id": str(parsed_styles)}])
                    updated = True
            except:
                new_styles = json.dumps([{"id": styles}])
                updated = True

        if updated:
            cursor.execute(
                "UPDATE adventure_templates SET selected_tone = ?, selected_image_styles = ? WHERE id = ?;",
                (new_tone, new_styles, row_id)
            )
    
    conn.commit()
    print("DB cleanup complete.")
finally:
    conn.close()
