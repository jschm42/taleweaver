from typing import Any

from pydantic import BaseModel, Field


class CharacterBase(BaseModel):
    name: str = Field(..., max_length=30)
    profile_image: str | None = None
    stats: dict[str, Any] | None = None
    strength: int | None = 10
    intelligence: int | None = 10
    wisdom: int | None = 10
    dexterity: int | None = 10
    charisma: int | None = 10
    armor_class: int | None = 10
    inventory: list[dict[str, Any]] | None = None
    equipment: dict[str, Any] | None = None
    status_effects: list[str] | None = None

class CharacterCreate(CharacterBase):
    pass

class CharacterUpdate(BaseModel):
    name: str | None = Field(None, max_length=30)
    profile_image: str | None = None
    stats: dict[str, Any] | None = None
    strength: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    dexterity: int | None = None
    charisma: int | None = None
    armor_class: int | None = None
    inventory: list[dict[str, Any]] | None = None
    equipment: dict[str, Any] | None = None
    status_effects: list[str] | None = None

class CharacterInDBBase(CharacterBase):
    id: str
    user_id: str

    model_config = {"from_attributes": True}

class CharacterSchema(CharacterInDBBase):
    pass
