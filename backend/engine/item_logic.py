from typing import Optional

def get_item_slot(name: str, item_type: str) -> Optional[str]:
    """
    Attempts to determine the appropriate equipment slot for an item based on its name and type.
    Returns None if the item is not equippable or no slot can be determined.
    """
    if not name or not item_type:
        return None
        
    type_upper = item_type.upper()
    name_lower = name.lower()
    
    # Weapons always go to Main_Hand by default
    if type_upper == "WEAPON":
        return "Main_Hand"
        
    if type_upper == "WEARABLE":
        # Hands / Arms
        if any(kw in name_lower for kw in ["bracers", "gauntlets", "gloves", "mittens", "vambrace", "armguard"]):
            return "Hands"
        # Head
        if any(kw in name_lower for kw in ["helmet", "cap", "circlet", "crown", "hood", "hat", "mask", "head"]):
            return "Head"
        # Chest
        if any(kw in name_lower for kw in ["armor", "chest", "cuirass", "vest", "tunic", "robe", "shirt", "breastplate", "plate"]):
            return "Chest"
        # Legs
        if any(kw in name_lower for kw in ["greaves", "leggings", "pants", "trousers", "breeches"]):
            return "Legs"
        # Feet
        if any(kw in name_lower for kw in ["boots", "shoes", "sandals", "slippers", "footwear"]):
            return "Feet"
        # Accessories
        if "ring" in name_lower or "band" in name_lower or "signet" in name_lower:
            return "Ring_1"
        if any(kw in name_lower for kw in ["amulet", "necklace", "pendant", "locket", "talisman"]):
            return "Amulet"
            
    # Tools might go to Off_Hand if they are held
    if type_upper == "TOOL":
        if any(kw in name_lower for kw in ["shield", "buckler", "torch", "lantern"]):
            return "Off_Hand"
        return "Main_Hand" # Pickaxes, hammers, etc.

    return None
