# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.main import app


# Initialize test client
client = TestClient(app)

# Mock user for authentication
MOCK_USER_ID = "test-user-id"
MOCK_USER_DATA = {
    "id": MOCK_USER_ID,
    "email": "test@example.com",
    "subscription_tier": "premium",
    "story_credits": 10
}


# Authentication dependency override
async def mock_get_current_user(request):
    return MOCK_USER_ID, MOCK_USER_DATA


# Apply the authentication override
app.dependency_overrides = {
    "get_current_user": mock_get_current_user
}


class TestAPI:
    """Test the API endpoints"""
    
    def test_health_check(self):
        """Test the health check endpoint"""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root(self):
        """Test the root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "message" in response.json()
    
    @patch("api.db.repositories.user_repository.UserRepository.get_user_by_id")
    def test_get_user_credits(self, mock_get_user):
        """Test getting user credits"""
        # Setup mock
        mock_get_user.return_value = {
            "id": MOCK_USER_ID,
            "story_credits": 10,
            "voice_credits": 5
        }
        
        # Make request
        response = client.get("/api/user/credits")
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["storyCredits"] == 10
        assert response.json()["voiceCredits"] == 5
    
    @patch("api.db.repositories.user_repository.UserRepository.check_subscription_features")
    def test_get_subscription_features(self, mock_check_features):
        """Test getting subscription features"""
        # Setup mock
        mock_check_features.return_value = {
            "success": True,
            "subscription_tier": "premium",
            "features": {
                "long_stories": True,
                "background_music": True,
                "custom_voices": True,
                "educational_themes": True,
                "story_sharing": False,
                "unlimited_storage": True,
                "max_images": 5
            }
        }
        
        # Make request
        response = client.get("/api/user/subscription")
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["subscription_tier"] == "premium"
        assert response.json()["features"]["long_stories"] is True
    
    @patch("api.db.repositories.story_repository.StoryRepository.get_stories_by_user")
    def test_get_stories(self, mock_get_stories):
        """Test listing stories"""
        # Setup mock
        mock_stories = [
            {
                "id": "story-1",
                "title": "Test Story 1",
                "theme": "adventure",
                "created_at": "2023-01-01T00:00:00Z"
            },
            {
                "id": "story-2",
                "title": "Test Story 2",
                "theme": "fantasy",
                "created_at": "2023-01-02T00:00:00Z"
            }
        ]
        mock_get_stories.return_value = (mock_stories, 2)
        
        # Make request
        response = client.get("/api/stories?limit=10&offset=0")
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert len(response.json()["stories"]) == 2
        assert response.json()["total"] == 2
    
    @patch("api.db.repositories.story_repository.StoryRepository.get_story_by_id")
    def test_get_story_by_id(self, mock_get_story):
        """Test getting a story by ID"""
        # Setup mock
        mock_story = {
            "id": "story-1",
            "title": "Test Story",
            "text_content": "Once upon a time...",
            "theme": "adventure",
            "language": "en",
            "duration": 60,
            "created_at": "2023-01-01T00:00:00Z",
            "audio_url": "https://example.com/audio.mp3",
            "is_favorite": False
        }
        mock_get_story.return_value = mock_story
        
        # Make request
        response = client.get("/api/stories/story-1")
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["story"]["id"] == "story-1"
        assert response.json()["story"]["title"] == "Test Story"
    
    @patch("api.db.repositories.story_repository.StoryRepository.update_story_favorite")
    def test_toggle_favorite(self, mock_update_favorite):
        """Test toggling favorite status"""
        # Setup mock
        mock_update_favorite.return_value = True
        
        # Make request
        response = client.post(
            "/api/stories/story-1/favorite",
            json={"isFavorite": True}
        )
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["isFavorite"] is True


class TestGenerationAPI:
    """Test the story generation API"""
    
    @patch("api.services.webhook_service.create_webhook_status")
    @patch("api.db.repositories.user_repository.UserRepository.check_user_credits")
    def test_async_story_generation(self, mock_check_credits, mock_create_status):
        """Test starting async story generation"""
        # Setup mocks
        mock_check_credits.return_value = {"has_credits": True, "story_credits": 5}
        mock_create_status.return_value = MagicMock()
        
        # Create test data
        test_data = {
            "images": ["data:image/jpeg;base64,/9j/4AAQSkZJ"],
            "characters": [{"name": "Test Character", "description": "A test character"}],
            "theme": "adventure",
            "duration": "short",
            "language": "english",
            "backgroundMusic": "calming"
        }
        
        # Mock the background task to prevent actual execution
        with patch("fastapi.BackgroundTasks.add_task") as mock_add_task:
            # Make request
            response = client.post("/api/stories/generate/webhook", json=test_data)
            
            # Verify response
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert "requestId" in response.json()
            
            # Verify background task was scheduled
            assert mock_add_task.called
    
    @patch("api.webhook_service.get_webhook_status")
    def test_get_generation_status(self, mock_get_status):
        """Test getting generation status"""
        # Setup mock
        mock_status = {
            "request_id": "test-request-id",
            "status": "processing",
            "progress": 0.5,
            "created_at": 123456789,
            "updated_at": 123456790
        }
        mock_get_status.return_value = mock_status
        
        # Make request
        response = client.get("/api/stories/status/test-request-id")
        
        # Verify response
        assert response.status_code == 200
        assert response.json()["requestId"] == "test-request-id"
        assert response.json()["status"] == "processing"
        assert response.json()["progress"] == 0.5


# Environment validation test
def test_environment_validation():
    """Test environment validation utility"""
    from api.utils.env_validator import validate_environment
    
    # Test with all required variables
    test_env = {key: "test-value" for key in [
        "SUPABASE_URL", 
        "SUPABASE_KEY", 
        "SUPABASE_SERVICE_ROLE_KEY",
        "ELEVENLABS_API_KEY",
        "HUGGINGFACE_API_TOKEN",
        "OPENAI_API_KEY",
        "SECRET_KEY"
    ]}
    
    errors = validate_environment(test_env, is_production=False)
    assert len(errors) == 0
    
    # Test with missing variables
    test_env.pop("ELEVENLABS_API_KEY")
    errors = validate_environment(test_env, is_production=False)
    assert len(errors) == 1
    
    # Test production requirements
    errors = validate_environment(test_env, is_production=True)
    assert len(errors) > 1  # Should include missing production vars


# Rate limiter tests
def test_rate_limiter():
    """Test rate limiting functionality"""
    from api.middleware.rate_limiter import RATE_LIMIT_RULES
    
    # Verify rate limit rules exist for different subscription tiers
    assert "free" in RATE_LIMIT_RULES
    assert "premium" in RATE_LIMIT_RULES
    assert "family" in RATE_LIMIT_RULES
    
    # Verify story generation has stricter limits than general endpoints
    assert RATE_LIMIT_RULES["free"]["story_generation"]["limit"] < RATE_LIMIT_RULES["free"]["general"]["limit"]
    assert RATE_LIMIT_RULES["premium"]["story_generation"]["limit"] > RATE_LIMIT_RULES["free"]["story_generation"]["limit"]