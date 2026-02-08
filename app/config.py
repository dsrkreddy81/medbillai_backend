from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = ""
    ANTHROPIC_API_KEY: str = ""
    UPLOAD_DIR: str = str(Path(__file__).resolve().parent.parent / "uploads")
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "document"

    model_config = {
        "env_file": [
            str(Path(__file__).resolve().parent.parent.parent / ".env.example"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ],
        "extra": "ignore",
    }


settings = Settings()
