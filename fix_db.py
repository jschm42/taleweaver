import sqlite3
import sys

def fix_db():
    conn = sqlite3.connect('taleweaver.db')
    c = conn.cursor()
    try:
        c.execute("DROP TABLE IF EXISTS characters")
        print("Dropped characters")
    except Exception as e:
        pass
    
    try:
        # SQLite doesn't easily drop columns, but let's see if we can drop the DB
        # or remove columns using alter table syntax in newer sqlite versions
        c.execute("ALTER TABLE adventures DROP COLUMN image_url")
        c.execute("ALTER TABLE adventures DROP COLUMN context")
        print("Dropped image_url and context")
    except Exception as e:
        print("Could not drop columns:", e)
        pass
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fix_db()
