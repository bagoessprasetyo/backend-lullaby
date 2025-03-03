# api/config.py
import os
from typing import List, Dict, Any, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import environment validator (after loading .env)
from utils.env_validator import load_defaults

# Load default values for optional environment variables
load_defaults()


class Settings(BaseSettings):
    # API configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Story Generation API"

    # Server configuration
    port: int = 8000  # Add this field
    log_level: str = "INFO"  # Add this field
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    # ElevenLabs
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    
    # HuggingFace
    HUGGINGFACE_API_TOKEN: str = os.getenv("HUGGINGFACE_API_TOKEN", "")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Storage
    STORAGE_URL: str = os.getenv("STORAGE_URL", "")
    TEMP_FOLDER: str = "temp"
    
    # Duration settings (in words)
    DURATION_SHORT_WORDS: int = 150
    DURATION_MEDIUM_WORDS: int = 400
    DURATION_LONG_WORDS: int = 700
    
    # Language mapping (to ISO code for TTS)
    LANGUAGE_MAP: Dict[str, str] = {
        "english": "en",
        "french": "fr",
        "japanese": "ja",
        "indonesian": "id"
    }
    
    # Background music paths
    MUSIC_PATHS: Dict[str, str] = {
        "calming": "background-music/gentle-lullaby.mp3",
        "soft": "background-music/dreamy-night.mp3",
        "peaceful": "background-music/ocean-waves.mp3",
        "soothing": "background-music/rainfall.mp3",
        "magical": "background-music/starlight-dreams.mp3"
    }
    
    # Default voices (ElevenLabs voice IDs)
    DEFAULT_VOICES: Dict[str, str] = {
        "ai-1": "21m00Tcm4TlvDq8ikWAM",  # Rachel
        "ai-2": "AZnzlk1XvdvUeBnXmlld",  # Domi
        "ai-3": "MF3mGyEYCl7XYWbV9V6O",  # Elli
        "ai-4": "TxGEqnHWrfWFTfGW9XjX"   # Josh
    }
    
    # CORS settings - simplified to avoid parsing errors
    CORS_ORIGINS_STR: str = os.getenv("CORS_ORIGINS", "*")
    
    # Use a property to convert the string to a list when needed
    @property
    def CORS_ORIGINS(self) -> List[str]:
        if self.CORS_ORIGINS_STR == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(",") if origin.strip()]
    
    # Redis (for distributed cache, rate limiting, etc.)
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Monitoring
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = ENVIRONMENT == "development"
    
    # Cache TTLs (in seconds)
    CACHE_TTL_SHORT: int = 60  # 1 minute
    CACHE_TTL_MEDIUM: int = 300  # 5 minutes
    CACHE_TTL_LONG: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Print mode on startup
print(f"Running in {settings.ENVIRONMENT.upper()} mode")

# Initialize monitoring in production
if settings.ENVIRONMENT == "production" and settings.SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[FastApiIntegration()]
        )
        print("Sentry monitoring initialized")
    except ImportError:
        print("Sentry SDK not installed, skipping initialization")
    except Exception as e:
        print(f"Error initializing Sentry: {str(e)}")