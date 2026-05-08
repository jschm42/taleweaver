import zipfile
import json
import os

path = r"c:\Users\jschmitz\DEV\git-repositories\taleweaver\adventures\default\The_Architect.adz"

try:
    with zipfile.ZipFile(path, "r") as z:
        if "adventure.adv" in z.namelist():
            with z.open("adventure.adv") as f:
                manifest = json.load(f)
                print(f"--- Checking {os.path.basename(path)} ---")
                for o in manifest.get("objects", []):
                    if "dagger" in o.get("name", "").lower() or "rusty" in o.get("name", "").lower():
                        print(f"Found object: {o.get('name')} (ID: {o.get('id')})")
                        print(f"Image URL: {o.get('image_url')}")
                prot = manifest.get("protagonist", {})
                for item in prot.get("starting_inventory", []):
                    if "dagger" in item.get("name", "").lower() or "rusty" in item.get("name", "").lower():
                        print(f"Found in inventory: {item.get('name')} (ID: {item.get('id')})")
                        print(f"Image URL: {item.get('image_url')}")
except Exception as e:
    print(f"Error reading {path}: {e}")
