import sqlite3
import os

DB_PATH = 'data/taleweaver.db'

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Add columns to avatars
    try:
        cursor.execute("ALTER TABLE avatars ADD COLUMN max_hp INTEGER DEFAULT 200")
        print("Added avatars.max_hp")
    except sqlite3.OperationalError as e:
        print(f"Skipping avatars.max_hp: {e}")

    try:
        cursor.execute("ALTER TABLE avatars ADD COLUMN max_stamina INTEGER DEFAULT 200")
        print("Added avatars.max_stamina")
    except sqlite3.OperationalError as e:
        print(f"Skipping avatars.max_stamina: {e}")

    try:
        cursor.execute("ALTER TABLE avatars ADD COLUMN max_mana INTEGER DEFAULT 200")
        print("Added avatars.max_mana")
    except sqlite3.OperationalError as e:
        print(f"Skipping avatars.max_mana: {e}")

    # Add columns to world_entities
    try:
        cursor.execute("ALTER TABLE world_entities ADD COLUMN max_hp INTEGER")
        print("Added world_entities.max_hp")
    except sqlite3.OperationalError as e:
        print(f"Skipping world_entities.max_hp: {e}")

    try:
        cursor.execute("ALTER TABLE world_entities ADD COLUMN max_mana INTEGER")
        print("Added world_entities.max_mana")
    except sqlite3.OperationalError as e:
        print(f"Skipping world_entities.max_mana: {e}")

    try:
        cursor.execute("ALTER TABLE world_entities ADD COLUMN max_stamina INTEGER")
        print("Added world_entities.max_stamina")
    except sqlite3.OperationalError as e:
        print(f"Skipping world_entities.max_stamina: {e}")

    # Update max values for existing records
    cursor.execute("UPDATE avatars SET max_hp = hp, max_stamina = stamina, max_mana = mana WHERE max_hp IS NULL OR max_hp = 200")
    cursor.execute("UPDATE world_entities SET max_hp = hp, max_mana = mana, max_stamina = stamina WHERE max_hp IS NULL")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
