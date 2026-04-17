from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class CharacterBase(BaseModel):
    name: str = Field(..., max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    strength: Optional[int] = 10
    intelligence: Optional[int] = 10
    wisdom: Optional[int] = 10
    dexterity: Optional[int] = 10
    charisma: Optional[int] = 10
    armor_class: Optional[int] = 10
    inventory: Optional[List[Dict[str, Any]]] = None
    equipment: Optional[Dict[str, Any]] = None
    status_effects: Optional[List[str]] = None

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    strength: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    dexterity: Optional[int] = None
    charisma: Optional[int] = None
    armor_class: Optional[int] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    equipment: Optional[Dict[str, Any]] = None
    status_effects: Optional[List[str]] = None

class CharacterInDBBase(CharacterBase):
    id: str
    user_id: str

    class Config:
        from_attributes = True

class CharacterSchema(CharacterInDBBase):
    pass
