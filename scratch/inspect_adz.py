import zipfile
import json
import os

adz_path = r"c:\Users\jschmitz\DEV\git-repositories\taleweaver\adventures\samples\The_Rat-Infested_Cellar_RPG_Mode_Test.adz"

with zipfile.ZipFile(adz_path, "r") as z:
    with z.open("adventure.adv") as f:
        manifest = json.load(f)
        
        # Search for Rusty Dagger in objects
        objects = manifest.get("objects", [])
        for o in objects:
            if "dagger" in o.get("name", "").lower():
                print(f"Found object: {o}")
        
        # Search in protagonist starting inventory
        protagonist = manifest.get("protagonist", {})
        inventory = protagonist.get("starting_inventory", [])
        for item in inventory:
            if "dagger" in item.get("name", "").lower():
                print(f"Found in inventory: {item}")
