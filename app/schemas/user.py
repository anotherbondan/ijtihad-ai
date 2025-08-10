from pydantic import BaseModel
from uuid import UUID

class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: UUID

    class Config:
        orm_mode = True
