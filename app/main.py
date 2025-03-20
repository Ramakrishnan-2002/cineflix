from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from .models import User, Review
from .routers import user,reviews,auth,movies,mail
from .config import settings
 # Encode password
DATABASE_URL = settings.DATABASE_URL

DATABASE_NAME = settings.DATABASE_NAME

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(DATABASE_URL)
    db = client[DATABASE_NAME]
    await init_beanie(database=db, document_models=[User, Review])
    yield
    client.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"]
)


app.include_router(user.router)
app.include_router(auth.router)
app.include_router(reviews.router)
app.include_router(movies.router)
app.include_router(mail.router)