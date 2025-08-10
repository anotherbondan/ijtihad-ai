from typing import List, Optional
from app.models import User
from uuid import UUID

async def get_all_users() -> List[User]:
    return await User.all()

async def get_user_by_id(user_id:UUID) -> Optional[User]:
    return await User.filter(id=user_id).first()

async def create_new_user(username: str, password: str, email:str) -> User:
    user = await User.create(username=username, password=password, email=email)
    return user