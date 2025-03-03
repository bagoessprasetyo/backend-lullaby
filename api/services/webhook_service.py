# api/services/webhook_service.py
import json
import uuid
import time
import asyncio
import httpx
from typing import Dict, Optional, Any, List
from pydantic import BaseModel

from config import settings
from utils.logger import get_logger
from db.repositories.story_repository import StoryRepository

logger = get_logger("webhook_service")

class WebhookStatus(BaseModel):
    """Status of a webhook request"""
    request_id: str
    status: str  # "pending", "processing", "completed", "failed"
    progress: float  # 0.0 to 1.0
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: int
    updated_at: int

# In-memory store for webhook statuses
# In production, use Redis or another distributed store
webhook_statuses: Dict[str, WebhookStatus] = {}


async def create_webhook_status(request_id: Optional[str] = None) -> WebhookStatus:
    """Create a new webhook status record"""
    if not request_id:
        request_id = str(uuid.uuid4())
        
    now = int(time.time())
    
    status = WebhookStatus(
        request_id=request_id,
        status="pending",
        progress=0.0,
        created_at=now,
        updated_at=now
    )
    
    webhook_statuses[request_id] = status
    return status


async def update_webhook_status(
    request_id: str,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    result: Optional[Dict] = None,
    error: Optional[str] = None
) -> WebhookStatus:
    """Update an existing webhook status"""
    if request_id not in webhook_statuses:
        logger.error(f"Webhook status not found: {request_id}")
        return None
        
    current = webhook_statuses[request_id]
    
    if status is not None:
        current.status = status
        
    if progress is not None:
        current.progress = progress
        
    if result is not None:
        current.result = result
        
    if error is not None:
        current.error = error
        
    current.updated_at = int(time.time())
    webhook_statuses[request_id] = current
    
    return current


async def get_webhook_status(request_id: str) -> Optional[WebhookStatus]:
    """Get the current status of a webhook request"""
    return webhook_statuses.get(request_id)


async def send_completion_webhook(
    callback_url: str,
    status: WebhookStatus
) -> bool:
    """Send a webhook notification when processing is complete"""
    try:
        if not callback_url:
            return False
            
        payload = {
            "request_id": status.request_id,
            "status": status.status,
            "result": status.result,
            "error": status.error,
            "completed_at": status.updated_at
        }
        
        # Add signature for security
        # In production, use a proper signing method
        signature = "placeholder-signature"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                callback_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": signature
                },
                timeout=10.0
            )
            
            if response.status_code in (200, 201, 202, 204):
                logger.info(f"Webhook sent successfully to {callback_url}")
                return True
            else:
                logger.error(f"Webhook failed: {response.status_code} {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error sending webhook: {str(e)}")
        return False


async def process_story_generation_async(
    request_id: str,
    user_id: str,
    request_data: Dict,
    callback_url: Optional[str] = None
) -> None:
    """Process story generation asynchronously with progress updates"""
    try:
        # Update status to processing
        await update_webhook_status(
            request_id=request_id,
            status="processing",
            progress=0.1
        )
        
        # Import services here to avoid circular imports
        from ..services import (
            image_service,
            story_service,
            speech_service,
            music_service
        )
        
        # 1. Process and store images
        await update_webhook_status(
            request_id=request_id,
            progress=0.2
        )
        
        image_paths = await image_service.store_images(
            user_id=user_id, 
            image_sources=request_data["images"]
        )
        
        if not image_paths:
            await update_webhook_status(
                request_id=request_id,
                status="failed",
                error="Failed to process images",
                progress=0.0
            )
            
            if callback_url:
                await send_completion_webhook(
                    callback_url=callback_url,
                    status=webhook_statuses[request_id]
                )
                
            return
        
        # 2. Analyze images
        await update_webhook_status(
            request_id=request_id,
            progress=0.3
        )
        
        scenarios = await image_service.analyze_multiple_images(request_data["images"])
        
        # 3. Generate story
        await update_webhook_status(
            request_id=request_id,
            progress=0.4
        )
        
        characters = [{"name": char["name"], "description": char["description"]} 
                      for char in request_data["characters"]]
        
        story_text, duration_seconds = await story_service.generate_story_from_scenarios(
            scenarios=scenarios,
            characters=characters,
            theme=request_data["theme"],
            duration=request_data["duration"],
            language=request_data["language"]
        )
        
        # 4. Generate title
        await update_webhook_status(
            request_id=request_id,
            progress=0.5
        )
        
        title = await story_service.generate_title(
            scenarios=scenarios,
            theme=request_data["theme"],
            language=request_data["language"]
        )
        
        # 5. Convert to speech
        await update_webhook_status(
            request_id=request_id,
            progress=0.6
        )
        
        voice_id = await speech_service.get_voice_id(request_data.get("voice", "ai-1"))
        
        speech_success, voice_path = await speech_service.generate_and_save_speech(
            text=story_text,
            voice_id=voice_id,
            user_id=user_id
        )
        
        if not speech_success:
            await update_webhook_status(
                request_id=request_id,
                status="failed",
                error=f"Failed to generate speech: {voice_path}",
                progress=0.0
            )
            
            if callback_url:
                await send_completion_webhook(
                    callback_url=callback_url,
                    status=webhook_statuses[request_id]
                )
                
            return
        
        # 6. Add background music if requested
        await update_webhook_status(
            request_id=request_id,
            progress=0.7
        )
        
        audio_path = voice_path
        background_music_id = None
        
        if request_data.get("backgroundMusic"):
            mix_success, mixed_path, music_info = await music_service.mix_audio_with_background(
                voice_path=voice_path,
                background_music_type=request_data["backgroundMusic"],
                user_id=user_id
            )
            
            if mix_success:
                audio_path = mixed_path
                background_music_id = music_info.get("id") if music_info else None
        
        # 7. Store story in database
        await update_webhook_status(
            request_id=request_id,
            progress=0.8
        )
        
        story_id = await StoryRepository.create_story(
            user_id=user_id,
            title=title,
            text_content=story_text,
            language=request_data["language"],
            theme=request_data["theme"],
            duration=duration_seconds,
            audio_url=f"{settings.SUPABASE_URL}/storage/v1/object/public/{audio_path}",
            storage_path=audio_path,
            background_music_id=background_music_id
        )
        
        if not story_id:
            await update_webhook_status(
                request_id=request_id,
                status="failed",
                error="Failed to store story in database",
                progress=0.0
            )
            
            if callback_url:
                await send_completion_webhook(
                    callback_url=callback_url,
                    status=webhook_statuses[request_id]
                )
                
            return
        
        # 8. Store characters and images
        await update_webhook_status(
            request_id=request_id,
            progress=0.9
        )
        
        await StoryRepository.add_story_characters(story_id, characters)
        await StoryRepository.add_story_images(story_id, user_id, image_paths)
        
        # 9. Complete the processing
        result = {
            "success": True,
            "storyId": story_id,
            "title": title,
            "textContent": story_text,
            "audioUrl": f"{settings.SUPABASE_URL}/storage/v1/object/public/{audio_path}",
            "duration": duration_seconds
        }
        
        await update_webhook_status(
            request_id=request_id,
            status="completed",
            progress=1.0,
            result=result
        )
        
        # 10. Send webhook if callback URL provided
        if callback_url:
            await send_completion_webhook(
                callback_url=callback_url,
                status=webhook_statuses[request_id]
            )
            
    except Exception as e:
        logger.error(f"Error in async story generation: {str(e)}")
        
        await update_webhook_status(
            request_id=request_id,
            status="failed",
            error=str(e),
            progress=0.0
        )
        
        if callback_url:
            await send_completion_webhook(
                callback_url=callback_url,
                status=webhook_statuses[request_id]
            )