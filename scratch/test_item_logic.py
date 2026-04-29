import sys
import os

# Add backend to path
sys.path.append(os.path.abspath("."))

from backend.engine.item_logic import get_item_slot

test_cases = [
    ("Steel Sword", "WEAPON", "Main_Hand"),
    ("Iron Helmet", "WEARABLE", "Head"),
    ("Leather Armor", "WEARABLE", "Chest"),
    ("Plate Gauntlets", "WEARABLE", "Hands"),
    ("Leather Boots", "WEARABLE", "Feet"),
    ("Magic Ring", "WEARABLE", "Ring_1"),
    ("Gold Amulet", "WEARABLE", "Amulet"),
    ("Wooden Shield", "TOOL", "Off_Hand"),
    ("Torch", "TOOL", "Off_Hand"),
    ("Stone", "PICKABLE", None),
]

print("Testing get_item_slot:")
for name, item_type, expected in test_cases:
    result = get_item_slot(name, item_type)
    status = "PASS" if result == expected else "FAIL"
    print(f"[{status}] {name} ({item_type}) -> {result} (Expected: {expected})")
