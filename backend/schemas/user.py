
from pydantic import BaseModel


class UserBase(BaseModel):
    username: str
    earned_awards: List[Dict[str, Any]] | None = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    username: str | None = None

class UserInDBBase(UserBase):
    id: str

    model_config = {"from_attributes": True}

class User(UserInDBBase):
    pass
