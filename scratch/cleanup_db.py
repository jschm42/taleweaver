import sqlite3

db_path = "data/taleweaver.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def remove_column(table, column):
    try:
        cursor.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        print(f"Dropped {column} from {table}")
    except Exception as e:
        print(f"Error dropping {column} from {table}: {e}")

cols_to_remove = ['plot', 'rules', 'walkthrough', 'completed_condition', 'gameover_condition', 'original_prompt', 'starting_timestamp']
for col in cols_to_remove:
    remove_column('adventure_templates', col)

# Also stamp back to previous version to be sure
# Actually, I'll just run it and then try upgrade again.

conn.commit()
conn.close()
