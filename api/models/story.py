# api/models/story.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


class ThemeEnum(str, Enum):
    ADVENTURE = "adventure"
    FANTASY = "fantasy"
    BEDTIME = "bedtime"
    EDUCATIONAL = "educational"
    CUSTOMIZED = "customized"


class DurationEnum(str, Enum):
    SHORT = "short"  # ~1 minute
    MEDIUM = "medium"  # ~3 minutes
    LONG = "long"  # ~5+ minutes


class LanguageEnum(str, Enum):
    ENGLISH = "english"
    FRENCH = "french"
    JAPANESE = "japanese"
    INDONESIAN = "indonesian"


class MusicEnum(str, Enum):
    CALMING = "calming"
    SOFT = "soft"
    PEACEFUL = "peaceful"
    SOOTHING = "soothing"
    MAGICAL = "magical"


class Character(BaseModel):
    name: str
    description: Optional[str] = None


class StoryGenerationRequest(BaseModel):
    images: List[str] = Field(..., description="Base64 encoded images or Supabase storage URLs")
    characters: List[Character] = Field(..., description="List of characters")
    theme: ThemeEnum = Field(..., description="Story theme")
    duration: DurationEnum = Field(..., description="Story duration")
    language: LanguageEnum = Field(..., description="Story language")
    backgroundMusic: Optional[MusicEnum] = Field(None, description="Background music type")
    voice: Optional[str] = Field(None, description="Voice ID for ElevenLabs or predefined voice")
    userId: str = Field(..., description="User ID for storage and credits management")


class WebhookGenerationRequest(BaseModel):
    images: List[str] = Field(..., description="Base64 encoded images or Supabase storage URLs")
    characters: List[Character] = Field(..., description="List of characters")
    theme: ThemeEnum = Field(..., description="Story theme")
    duration: DurationEnum = Field(..., description="Story duration")
    language: LanguageEnum = Field(..., description="Story language")
    backgroundMusic: Optional[MusicEnum] = Field(None, description="Background music type")
    voice: Optional[str] = Field(None, description="Voice ID for ElevenLabs or predefined voice")
    callback_url: Optional[HttpUrl] = Field(None, description="URL to call when processing is complete")


class StoryGenerationResponse(BaseModel):
    success: bool
    storyId: Optional[str] = None
    title: Optional[str] = None
    textContent: Optional[str] = None
    audioUrl: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None


class StoryDetailResponse(BaseModel):
    id: str
    title: str
    text_content: str
    language: str
    theme: str
    duration: int
    audio_url: str
    created_at: str
    is_favorite: bool
    play_count: int
    images: List[Dict[str, Any]]
    characters: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[Dict[str, str]]] = None


class StoryListResponse(BaseModel):
    success: bool
    stories: List[StoryDetailResponse]
    total: int
    limit: int
    offset: int


class GenerationStatusResponse(BaseModel):
    requestId: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: float  # 0.0 to 1.0
    createdAt: int
    updatedAt: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class UserCreditsResponse(BaseModel):
    storyCredits: int
    voiceCredits: int


class FeatureResponse(BaseModel):
    long_stories: bool
    background_music: bool
    custom_voices: bool
    educational_themes: bool
    story_sharing: bool
    unlimited_storage: bool
    max_images: int


class SubscriptionResponse(BaseModel):
    success: bool
    subscription_tier: str
    features: FeatureResponse