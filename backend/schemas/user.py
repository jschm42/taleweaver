from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: Optional[str] = None

class UserInDBBase(UserBase):
    id: str

    model_config = {"from_attributes": True}

class User(UserInDBBase):
    pass
