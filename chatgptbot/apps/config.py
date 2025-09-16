import os
from pydantic import BaseModel
from dotenv import load_dotenv; 
load_dotenv()
class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret")

settings = Settings()
