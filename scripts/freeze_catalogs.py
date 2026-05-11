import json
import os
import shutil
import sqlite3
from pprint import pformat

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "taleweaver.db")
DEFAULTS_FILE = os.path.join(BASE_DIR, "backend", "core", "catalog_defaults.py")
STATIC_ASSETS_DIR = os.path.join(BASE_DIR, "backend", "static", "assets", "catalog")
DATA_CATALOG_DIR = os.path.join(BASE_DIR, "data", "catalog")

def freeze():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"[*] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find the admin user
    cursor.execute("SELECT id, image_styles_catalog, tone_catalog FROM users WHERE role = 'admin' LIMIT 1")
    admin = cursor.fetchone()

    if not admin:
        # Fallback to the first user if no admin found
        cursor.execute("SELECT id, image_styles_catalog, tone_catalog FROM users LIMIT 1")
        admin = cursor.fetchone()

    if not admin:
        print("Error: No user found in database to extract catalogs from.")
        conn.close()
        return

    print(f"[*] Extracting catalogs from user {admin['id']}")
    
    try:
        styles = json.loads(admin['image_styles_catalog']) if admin['image_styles_catalog'] else []
        tones = json.loads(admin['tone_catalog']) if admin['tone_catalog'] else []
    except Exception as e:
        print(f"Error parsing catalogs: {e}")
        conn.close()
        return

    def process_catalog(items, subfolder):
        processed = []
        for item in items:
            img_url = item.get("image_url")
            if img_url and img_url.startswith("/data/catalog/"):
                # Move file to static assets
                filename = os.path.basename(img_url)
                src_path = os.path.join(BASE_DIR, "data", "catalog", subfolder, filename)
                dest_dir = os.path.join(STATIC_ASSETS_DIR, subfolder)
                dest_path = os.path.join(dest_dir, filename)

                if os.path.exists(src_path):
                    os.makedirs(dest_dir, exist_ok=True)
                    print(f"[*] Copying {filename} to permanent assets...")
                    shutil.copy2(src_path, dest_path)
                    item["image_url"] = f"/assets/catalog/{subfolder}/{filename}"
                else:
                    print(f"Warning: Image file not found at {src_path}")
            
            processed.append(item)
        return processed

    print("[*] Processing styles...")
    final_styles = process_catalog(styles, "styles")
    print("[*] Processing tones...")
    final_tones = process_catalog(tones, "tones")

    # Generate the Python file
    content = f"""from typing import Any

DEFAULT_IMAGE_STYLES: list[dict[str, Any]] = {pformat(final_styles, indent=4)}

DEFAULT_TONES: list[dict[str, Any]] = {pformat(final_tones, indent=4)}
"""

    print(f"[*] Updating {DEFAULTS_FILE}...")
    with open(DEFAULTS_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print("[+] Successfully frozen catalogs as defaults!")
    conn.close()

if __name__ == "__main__":
    freeze()
