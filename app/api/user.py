from fastapi import APIRouter, HTTPException
from app.schemas.user import UserResponse, UserCreate
from app.crud.user import get_all_users, create_user, get_user_by_id
from typing import List


# Define API Router
router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def get_users():
    try: 
        users = await get_all_users()
        return users
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id):
    try: 
        user = await get_user_by_id(user_id)
        return user
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=UserResponse)
async def create_new_user(request: UserCreate): 
    try: 
        user = await create_user(request.username, request.password, request.email)
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))