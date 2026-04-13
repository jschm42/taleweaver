from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class CharacterBase(BaseModel):
    name: str = Field(..., max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    inventory: Optional[List[Dict[str, Any]]] = None
    equipment: Optional[Dict[str, Any]] = None
    status_effects: Optional[List[str]] = None

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=30)
    profile_image: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
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
