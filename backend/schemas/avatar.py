from typing import Any

from pydantic import BaseModel


class AvatarBase(BaseModel):
    name: str
    role: str | None = None
    description: str | None = None
    profile_image: str | None = None
    hp: int | None = 200
    stamina: int | None = 200
    mana: int | None = 200
    strength: int | None = 10
    intelligence: int | None = 10
    wisdom: int | None = 10
    dexterity: int | None = 10
    charisma: int | None = 10
    armor_class: int | None = 10
    stats: dict[str, Any] | None = None
    inventory: list[dict[str, Any]] | None = None
    equipment: dict[str, Any] | None = None
    status_effects: list[str] | None = None

class AvatarCreate(AvatarBase):
    user_id: str

class AvatarUpdate(BaseModel):
    name: str | None = None
    hp: int | None = None
    stamina: int | None = None
    mana: int | None = None
    strength: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    dexterity: int | None = None
    charisma: int | None = None
    armor_class: int | None = None
    stats: dict[str, Any] | None = None
    inventory: list[dict[str, Any]] | None = None
    equipment: dict[str, Any] | None = None
    status_effects: list[str] | None = None

class AvatarInDBBase(AvatarBase):
    id: str
    user_id: str

    model_config = {"from_attributes": True}

class Avatar(AvatarInDBBase):
    pass
