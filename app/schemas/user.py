from pydantic import BaseModel, EmailStr
from uuid import UUID

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str 

class UserResponse(UserBase):
    id: UUID

    class Config:
        orm_mode = True
