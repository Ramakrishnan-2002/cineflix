from fastapi import APIRouter,status,Depends,HTTPException,status
from ..schemas import UserCreate,UserResponseModel
from ..models import User
from ..utils import hash
from ..OAuth2 import get_current_user



router=APIRouter(prefix="/users",tags=['users'])

@router.post("/createuser",status_code=status.HTTP_201_CREATED)
async def create_user(user:UserCreate):
    try:
        existing_user=await User.find_one(User.email==user.email)
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="User already created")
        user.password=hash(user.password)
        new_user=User(**user.model_dump())
        await new_user.insert()
        return {"Success":"Signup successfull"}
    except Exception as e:
        error=f"Signup failed: {str(e)}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=error)


@router.get("/getallusers",response_model=list[UserResponseModel])
async def get_all():
    users=await User.find_all().to_list()
    return users

@router.delete("/deleteuser",status_code=status.HTTP_200_OK)
async def delete_user(user=Depends(get_current_user)):
    try:
        existing_user = await User.find_one(User.email == user.email)   
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        await existing_user.delete()
    except Exception as e:
        error=f"Deletion failed: {str(e)}"
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=error)
    return {"Success": "User deleted successfully"}