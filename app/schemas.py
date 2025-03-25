from typing import List
from pydantic import BaseModel,EmailStr, Field
from datetime import datetime
from beanie import PydanticObjectId


class UserCreate(BaseModel):
    name:str
    email:EmailStr
    password:str 

class UserResponseModel(BaseModel):
    id: PydanticObjectId
    name: str
    email: EmailStr
    created_at:datetime 


class Token(BaseModel):
    access_token:str
    token_type:str


class TokenResponseData(BaseModel):
    id: PydanticObjectId
    email :EmailStr


class ReviewCreateModel(BaseModel):
    movie_name:str
    release_date:str
    review_content:str
    rating: float = Field(..., ge=0, le=5, description="Rating must be between 0 and 5")
class ReviewEditModel(BaseModel):
    review_content:str
    rating: float = Field(..., ge=0, le=5, description="Rating must be between 0 and 5")

class ReviewItemResponseModel(BaseModel):
    review_content: str
    rating: int
    created_by: PydanticObjectId  # User ID reference
    created_at: datetime

class ReviewResponseModel(BaseModel):
    movie_name: str
    release_date: str
    overall_rating: float
    reviews: List[ReviewItemResponseModel]



class MovieBasic(BaseModel):
    title: str
    poster: str
    release_date: str
    overview: str
    url: str

class MovieDetails(BaseModel):
    director: str | None
    cast: list
    genres: list
    runtime: str
    certificate: str
    language: str
    watch_link: list
    backdrops: list
    overview :str


class ForgotEmail(BaseModel):
    email:EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str