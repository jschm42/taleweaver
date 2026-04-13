import sqlite3

def check_images():
    conn = sqlite3.connect('taleweaver.db')
    cursor = conn.cursor()
    
    print("--- ADVENTURES ---")
    cursor.execute("SELECT id, title, image_url, is_ready, creation_error FROM adventures")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Title: {row[1]}, URL: {row[2]}, Ready: {row[3]}, Error: {row[4]}")
        
    print("\n--- ENTITIES ---")
    cursor.execute("SELECT id, name, entity_type, image_url, adventure_id FROM world_entities LIMIT 10")
    for row in cursor.fetchall():
        print(f"ID: {row[0]}, Name: {row[1]}, Type: {row[2]}, URL: {row[3]}, AdvID: {row[4]}")
        
    conn.close()

if __name__ == "__main__":
    check_images()
