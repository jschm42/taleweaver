import sqlite3
import os

# Possible Database paths
DB_PATHS = ["taleweaver.db", "backend/taleweaver.db"]

def migrate():
    found_db = None
    for path in DB_PATHS:
        if os.path.exists(path):
            found_db = path
            break
            
    if not found_db:
        print(f"No database found in {DB_PATHS}. Skipping DB migration.")
        return

    print(f"Migrating database: {found_db}")
    conn = sqlite3.connect(found_db)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Found tables: {tables}")

    try:
        # Update characters
        if "characters" in tables:
            print("Updating character profile images...")
            cursor.execute("UPDATE characters SET profile_image = REPLACE(profile_image, '/uploads/', '/data/characters/') WHERE profile_image LIKE '/uploads/%'")
            print(f"Updated {cursor.rowcount} characters.")

        # Update adventures
        if "adventures" in tables:
            print("Updating adventure images...")
            cursor.execute("UPDATE adventures SET image_url = REPLACE(image_url, '/uploads/', '/data/adventures/') WHERE image_url LIKE '/uploads/%'")
            print(f"Updated {cursor.rowcount} adventures.")

        # Update world_entities
        if "world_entities" in tables:
            print("Updating world entity images...")
            cursor.execute("UPDATE world_entities SET image_url = REPLACE(image_url, '/uploads/', '/data/') WHERE image_url LIKE '/uploads/%'")
            print(f"Updated {cursor.rowcount} world entities.")

        conn.commit()
        print("Database path migration completed successfully.")
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
