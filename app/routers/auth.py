from typing import Annotated
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from ..schemas import Token
from ..models import User
from ..utils import verify
from ..OAuth2 import create_access_token

router = APIRouter(
    prefix="/logins",
    tags=["Authentication"]
)

@router.post("/token", status_code=status.HTTP_200_OK, response_model=Token)
async def login(user_cred: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = await User.find_one(User.email == user_cred.username)

    if not user or not verify(user_cred.password, user.password):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials. Please try again!")

    access_token = create_access_token(data={"id": str(user.id), "email": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
