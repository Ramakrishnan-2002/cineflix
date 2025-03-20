from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_NAME: str

    class Config:
        env_file = ".env"  # Load environment variables from .env file

settings = Settings()
