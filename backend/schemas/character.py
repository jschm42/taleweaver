from typing import Any, Optional

from pydantic import BaseModel, Field


class CharacterBase(BaseModel):
    name: str = Field(..., max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[dict[str, Any]] = None
    strength: Optional[int] = 10
    intelligence: Optional[int] = 10
    wisdom: Optional[int] = 10
    dexterity: Optional[int] = 10
    charisma: Optional[int] = 10
    armor_class: Optional[int] = 10
    inventory: Optional[list[dict[str, Any]]] = None
    equipment: Optional[dict[str, Any]] = None
    status_effects: Optional[list[str]] = None

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[dict[str, Any]] = None
    strength: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    dexterity: Optional[int] = None
    charisma: Optional[int] = None
    armor_class: Optional[int] = None
    inventory: Optional[list[dict[str, Any]]] = None
    equipment: Optional[dict[str, Any]] = None
    status_effects: Optional[list[str]] = None

class CharacterInDBBase(CharacterBase):
    id: str
    user_id: str

    model_config = {"from_attributes": True}

class CharacterSchema(CharacterInDBBase):
    pass
