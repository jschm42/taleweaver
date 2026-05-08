import zipfile
import json
import os

samples_dir = r"c:\Users\jschmitz\DEV\git-repositories\taleweaver\adventures\samples"

for filename in os.listdir(samples_dir):
    if filename.endswith(".adz"):
        path = os.path.join(samples_dir, filename)
        try:
            with zipfile.ZipFile(path, "r") as z:
                with z.open("adventure.adv") as f:
                    manifest = json.load(f)
                    print(f"--- Checking {filename} ---")
                    for o in manifest.get("objects", []):
                        if "dagger" in o.get("name", "").lower():
                            print(f"Found object: {o}")
                    prot = manifest.get("protagonist", {})
                    for item in prot.get("starting_inventory", []):
                        if "dagger" in item.get("name", "").lower():
                            print(f"Found in inventory: {item}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")
    elif filename.endswith(".adv"):
        path = os.path.join(samples_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                print(f"--- Checking {filename} ---")
                for o in manifest.get("objects", []):
                    if "dagger" in o.get("name", "").lower():
                        print(f"Found object: {o}")
                prot = manifest.get("protagonist", {})
                for item in prot.get("starting_inventory", []):
                    if "dagger" in item.get("name", "").lower():
                        print(f"Found in inventory: {item}")
        except Exception as e:
            print(f"Error reading {filename}: {e}")
