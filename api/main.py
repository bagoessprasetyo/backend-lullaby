# api/main.py
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Header, Request, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import asyncio
import time
import os
import json
import uuid

from config import settings
from models.story import (
    StoryGenerationRequest, 
    StoryGenerationResponse,
    WebhookGenerationRequest
)
from utils.logger import get_logger
from services import (
    image_service,
    story_service,
    speech_service,
    music_service,
    auth_service,
    webhook_service,
    websocket_service
)
from db.repositories.story_repository import StoryRepository
from db.repositories.user_repository import UserRepository
from middleware.rate_limiter import RateLimiter

# Initialize logger
logger = get_logger("api")

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.2.0",
    description="Story Generation API for children's stories"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(RateLimiter)

# Create necessary directories
os.makedirs(settings.TEMP_FOLDER, exist_ok=True)
os.makedirs("logs", exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Run tasks on startup"""
    # Start background task to clean up rate limits
    asyncio.create_task(RateLimiter.cleanup_rate_limits())


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Story Generation API",
        "version": "0.2.0",
        "docs": "/docs"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "timestamp": time.time()
    }


async def get_current_user(request: Request) -> tuple:
    """Get current user from request"""
    return await auth_service.get_current_user(request)


@app.post("/api/stories/generate", response_model=StoryGenerationResponse)
async def generate_story(
    request: StoryGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: tuple = Depends(get_current_user)
):
    """Generate a story based on images and parameters"""
    user_id, user_data = current_user
    start_time = time.time()
    logger.info(f"Story generation request received for user {user_id}")
    
    try:
        # Verify user has credits
        credits_info = await UserRepository.check_user_credits(user_id)
        
        if not credits_info["has_credits"]:
            return StoryGenerationResponse(
                success=False,
                error=f"Story generation failed: {credits_info['reason']}"
            )
        
        # Check subscription features for premium content
        if request.duration.value == "long" or request.backgroundMusic is not None:
            features = await UserRepository.check_subscription_features(user_id)
            
            if not features["success"]:
                return StoryGenerationResponse(
                    success=False,
                    error=f"Failed to check subscription: {features.get('reason')}"
                )
                
            if request.duration.value == "long" and not features["features"]["long_stories"]:
                return StoryGenerationResponse(
                    success=False,
                    error="Long stories require a premium subscription"
                )
                
            if request.backgroundMusic is not None and not features["features"]["background_music"]:
                return StoryGenerationResponse(
                    success=False,
                    error="Background music requires a premium subscription"
                )
        
        # Process images
        logger.info("Processing images")
        image_paths = await image_service.store_images(user_id, request.images)
        
        if not image_paths:
            return StoryGenerationResponse(
                success=False,
                error="Failed to process images"
            )
        
        # Analyze images
        logger.info("Analyzing images")
        scenarios = await image_service.analyze_multiple_images(request.images)
        
        # Generate story
        logger.info("Generating story")
        characters = [{"name": char.name, "description": char.description} for char in request.characters]
        
        story_text, duration_seconds = await story_service.generate_story_from_scenarios(
            scenarios=scenarios,
            characters=characters,
            theme=request.theme.value,
            duration=request.duration.value,
            language=request.language.value
        )
        
        # Generate title
        logger.info("Generating title")
        title = await story_service.generate_title(
            scenarios=scenarios,
            theme=request.theme.value,
            language=request.language.value
        )
        
        # Convert text to speech
        logger.info("Converting text to speech")
        voice_id = await speech_service.get_voice_id(request.voice or "ai-1")
        
        speech_success, voice_path = await speech_service.generate_and_save_speech(
            text=story_text,
            voice_id=voice_id,
            user_id=user_id
        )
        
        if not speech_success:
            return StoryGenerationResponse(
                success=False,
                error=f"Failed to generate speech: {voice_path}"
            )
        
        # Add background music if requested
        audio_path = voice_path
        background_music_id = None
        
        if request.backgroundMusic:
            logger.info(f"Adding background music: {request.backgroundMusic}")
            
            mix_success, mixed_path, music_info = await music_service.mix_audio_with_background(
                voice_path=voice_path,
                background_music_type=request.backgroundMusic.value,
                user_id=user_id
            )
            
            if mix_success:
                audio_path = mixed_path
                background_music_id = music_info.get("id") if music_info else None
        
        # Store story in database
        logger.info("Storing story in database")
        story_id = await StoryRepository.create_story(
            user_id=user_id,
            title=title,
            text_content=story_text,
            language=request.language.value,
            theme=request.theme.value,
            duration=duration_seconds,
            audio_url=f"{settings.SUPABASE_URL}/storage/v1/object/public/{audio_path}",
            storage_path=audio_path,
            background_music_id=background_music_id
        )
        
        if not story_id:
            return StoryGenerationResponse(
                success=False,
                error="Failed to store story in database"
            )
        
        # Store character information
        await StoryRepository.add_story_characters(story_id, characters)
        
        # Store image information
        await StoryRepository.add_story_images(story_id, user_id, image_paths)
        
        # Generate tags based on theme and content
        tags = [request.theme.value, request.language.value]
        if request.backgroundMusic:
            tags.append(f"music:{request.backgroundMusic.value}")
        
        # Store tags
        await StoryRepository.add_story_tags(story_id, tags)
        
        # Decrement user credits (asynchronously)
        background_tasks.add_task(UserRepository.decrement_story_credits, user_id)
        
        # Record generation statistics
        # TODO: Implement analytics tracking
        
        # Return response
        processing_time = time.time() - start_time
        logger.info(f"Story generation completed in {processing_time:.2f} seconds")
        
        return StoryGenerationResponse(
            success=True,
            storyId=story_id,
            title=title,
            textContent=story_text,
            audioUrl=f"{settings.SUPABASE_URL}/storage/v1/object/public/{audio_path}",
            duration=duration_seconds
        )
        
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        return StoryGenerationResponse(
            success=False,
            error=f"Story generation failed: {str(e)}"
        )


@app.post("/api/stories/generate/webhook")
async def generate_story_webhook(
    request: WebhookGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: tuple = Depends(get_current_user)
):
    """Generate a story asynchronously with webhook notification"""
    user_id, user_data = current_user
    
    try:
        # Verify user has credits
        credits_info = await UserRepository.check_user_credits(user_id)
        
        if not credits_info["has_credits"]:
            return {
                "success": False,
                "error": f"Story generation failed: {credits_info['reason']}"
            }
        
        # Create request ID
        request_id = str(uuid.uuid4())
        
        # Initialize webhook status
        await webhook_service.create_webhook_status(request_id)
        
        # Convert request model to dict
        request_data = {
            "images": request.images,
            "characters": [{"name": char.name, "description": char.description} for char in request.characters],
            "theme": request.theme.value,
            "duration": request.duration.value,
            "language": request.language.value,
            "backgroundMusic": request.backgroundMusic.value if request.backgroundMusic else None,
            "voice": request.voice or "ai-1",
            "userId": user_id
        }
        
        # Start asynchronous processing
        background_tasks.add_task(
            webhook_service.process_story_generation_async,
            request_id=request_id,
            user_id=user_id,
            request_data=request_data,
            callback_url=request.callback_url
        )
        
        # Return request ID for status checking
        return {
            "success": True,
            "requestId": request_id,
            "message": "Story generation started. Check status with /api/stories/status/{request_id}"
        }
    
    except Exception as e:
        logger.error(f"Error starting webhook story generation: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to start story generation: {str(e)}"
        }


@app.get("/api/stories/status/{request_id}")
async def get_story_status(
    request_id: str,
    current_user: tuple = Depends(get_current_user)
):
    """Get status of an asynchronous story generation request"""
    user_id, user_data = current_user
    
    try:
        status = await webhook_service.get_webhook_status(request_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Request ID not found")
            
        return {
            "requestId": status.request_id,
            "status": status.status,
            "progress": status.progress,
            "createdAt": status.created_at,
            "updatedAt": status.updated_at,
            "result": status.result,
            "error": status.error
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting story status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting status: {str(e)}")


@app.get("/api/stories/{story_id}")
async def get_story(
    story_id: str, 
    current_user: tuple = Depends(get_current_user)
):
    """Get a story by ID"""
    user_id, user_data = current_user
    
    try:
        # Get story from database
        story = await StoryRepository.get_story_by_id(story_id, user_id)
        
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        
        return {
            "success": True,
            "story": story
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving story: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving story: {str(e)}")


@app.get("/api/stories")
async def get_user_stories(
    limit: int = 10,
    offset: int = 0,
    theme: Optional[str] = None,
    language: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    search: Optional[str] = None,
    order_by: str = "created_at:desc",
    current_user: tuple = Depends(get_current_user)
):
    """Get stories for the current user with filtering and pagination"""
    user_id, user_data = current_user
    
    try:
        # Prepare filters
        filters = {}
        
        if theme:
            filters["theme"] = theme
            
        if language:
            filters["language"] = language
            
        if is_favorite is not None:
            filters["is_favorite"] = is_favorite
            
        if search:
            filters["search"] = search
            
        if order_by:
            filters["order_by"] = order_by
        
        # Get stories from database
        stories, count = await StoryRepository.get_stories_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
            filters=filters
        )
        
        return {
            "success": True,
            "stories": stories,
            "total": count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting stories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting stories: {str(e)}")


@app.post("/api/stories/{story_id}/favorite")
async def toggle_favorite(
    story_id: str,
    favorite_data: Dict[str, bool],
    current_user: tuple = Depends(get_current_user)
):
    """Toggle favorite status for a story"""
    user_id, user_data = current_user
    
    try:
        is_favorite = favorite_data.get("isFavorite", False)
        
        success = await StoryRepository.update_story_favorite(
            story_id=story_id,
            user_id=user_id,
            is_favorite=is_favorite
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Story not found")
            
        return {
            "success": True,
            "isFavorite": is_favorite
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error toggling favorite: {str(e)}")


@app.post("/api/stories/{story_id}/played")
async def record_play(
    story_id: str,
    play_data: Dict[str, Any],
    current_user: tuple = Depends(get_current_user)
):
    """Record play history for a story"""
    user_id, user_data = current_user
    
    try:
        completed = play_data.get("completed", False)
        progress_percentage = play_data.get("progressPercentage", 0)
        
        play_id = await StoryRepository.record_play_history(
            user_id=user_id,
            story_id=story_id,
            completed=completed,
            progress_percentage=progress_percentage
        )
        
        if not play_id:
            raise HTTPException(status_code=500, detail="Failed to record play history")
            
        return {
            "success": True,
            "playId": play_id
        }
    except Exception as e:
        logger.error(f"Error recording play history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error recording play history: {str(e)}")


@app.delete("/api/stories/{story_id}")
async def delete_story(
    story_id: str,
    current_user: tuple = Depends(get_current_user)
):
    """Delete a story"""
    user_id, user_data = current_user
    
    try:
        success = await StoryRepository.delete_story(
            story_id=story_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Story not found")
            
        return {
            "success": True,
            "message": "Story deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting story: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting story: {str(e)}")


@app.get("/api/user/subscription")
async def get_subscription_features(
    current_user: tuple = Depends(get_current_user)
):
    """Get subscription features for the current user"""
    user_id, user_data = current_user
    
    try:
        features = await UserRepository.check_subscription_features(user_id)
        
        if not features["success"]:
            raise HTTPException(
                status_code=500, 
                detail=features.get("reason", "Failed to check subscription")
            )
            
        return features
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription features: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting subscription features: {str(e)}")


@app.get("/api/user/credits")
async def get_user_credits(
    current_user: tuple = Depends(get_current_user)
):
    """Get credits for the current user"""
    user_id, user_data = current_user
    
    try:
        user = await UserRepository.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return {
            "storyCredits": user.get("story_credits", 0),
            "voiceCredits": user.get("voice_credits", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user credits: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting user credits: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)