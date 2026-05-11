from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    earned_awards: Optional[List[Dict[str, Any]]] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None

class UserInDBBase(UserBase):
    id: str

    model_config = {"from_attributes": True}

class User(UserInDBBase):
    pass
