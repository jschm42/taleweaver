from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class AvatarBase(BaseModel):
    name: str
    role: Optional[str] = None
    description: Optional[str] = None
    profile_image: Optional[str] = None
    hp: Optional[int] = 200
    stamina: Optional[int] = 200
    mana: Optional[int] = 200
    strength: Optional[int] = 10
    intelligence: Optional[int] = 10
    wisdom: Optional[int] = 10
    dexterity: Optional[int] = 10
    charisma: Optional[int] = 10
    armor_class: Optional[int] = 10
    stats: Optional[Dict[str, Any]] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    equipment: Optional[Dict[str, Any]] = None
    status_effects: Optional[List[str]] = None

class AvatarCreate(AvatarBase):
    user_id: str

class AvatarUpdate(BaseModel):
    name: Optional[str] = None
    hp: Optional[int] = None
    stamina: Optional[int] = None
    mana: Optional[int] = None
    strength: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    dexterity: Optional[int] = None
    charisma: Optional[int] = None
    armor_class: Optional[int] = None
    stats: Optional[Dict[str, Any]] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    equipment: Optional[Dict[str, Any]] = None
    status_effects: Optional[List[str]] = None

class AvatarInDBBase(AvatarBase):
    id: str
    user_id: str

    class Config:
        from_attributes = True

class Avatar(AvatarInDBBase):
    pass
