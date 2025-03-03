# api/db/supabase.py
import os
import uuid
import asyncio
from typing import Dict, List, Optional, Any
from supabase import create_client, Client
from config import settings
from utils.logger import get_logger

logger = get_logger("supabase")

# Initialize Supabase client
supabase: Client = create_client(
    settings.SUPABASE_URL, 
    settings.SUPABASE_KEY
)

# Initialize admin client for privileged operations
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_ROLE_KEY
)


async def get_user_profile(user_id: str) -> Dict:
    """Get user profile from Supabase"""
    try:
        response = supabase.table("profiles").select("*").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        return None


async def check_user_credits(user_id: str) -> Dict:
    """Check if user has enough credits to generate a story"""
    try:
        user = await get_user_profile(user_id)
        
        if not user:
            return {"has_credits": False, "reason": "User not found"}
        
        if user.get("story_credits", 0) <= 0:
            return {"has_credits": False, "reason": "Insufficient story credits"}
        
        subscription_tier = user.get("subscription_tier", "free")
        
        return {
            "has_credits": True,
            "story_credits": user.get("story_credits", 0),
            "subscription_tier": subscription_tier
        }
    except Exception as e:
        logger.error(f"Error checking user credits: {str(e)}")
        return {"has_credits": False, "reason": str(e)}


async def decrement_story_credits(user_id: str) -> bool:
    """Decrement user's story credits"""
    try:
        # This is handled by a database trigger in Supabase
        # But we'll decrement it manually here for safety
        user = await get_user_profile(user_id)
        
        if not user or user.get("story_credits", 0) <= 0:
            return False
        
        credits = user.get("story_credits", 0) - 1
        
        response = supabase.table("profiles").update({
            "story_credits": credits
        }).eq("id", user_id).execute()
        
        return True
    except Exception as e:
        logger.error(f"Error decrementing story credits: {str(e)}")
        return False


async def upload_file_to_storage(
    bucket_name: str, 
    file_data: bytes, 
    file_path: str, 
    content_type: str
) -> str:
    """Upload file to Supabase storage"""
    try:
        response = supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_data,
            file_options={"content-type": content_type}
        )
        
        # Generate public URL
        file_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        return file_url
    except Exception as e:
        logger.error(f"Error uploading file to storage: {str(e)}")
        return None


async def insert_story(
    user_id: str,
    title: str,
    text_content: str,
    language: str,
    theme: str,
    duration: int,
    audio_url: str,
    storage_path: str = None,
    background_music_id: str = None
) -> Optional[str]:
    """Insert story record in Supabase"""
    try:
        story_data = {
            "user_id": user_id,
            "title": title,
            "text_content": text_content,
            "language": settings.LANGUAGE_MAP.get(language, "en"),
            "theme": theme,
            "duration": duration,
            "audio_url": audio_url,
            "storage_path": storage_path,
            "background_music_id": background_music_id
        }
        
        response = supabase.table("stories").insert(story_data).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]["id"]
        
        return None
    except Exception as e:
        logger.error(f"Error inserting story: {str(e)}")
        return None


async def insert_characters(story_id: str, characters: List[Dict]) -> bool:
    """Insert character records for a story"""
    try:
        characters_data = [
            {
                "story_id": story_id,
                "name": character["name"],
                "description": character.get("description", "")
            }
            for character in characters
        ]
        
        # Insert characters in batches to avoid issues with large lists
        for i in range(0, len(characters_data), 10):
            batch = characters_data[i:i+10]
            response = supabase.table("characters").insert(batch).execute()
        
        return True
    except Exception as e:
        logger.error(f"Error inserting characters: {str(e)}")
        return False


async def insert_story_images(story_id: str, user_id: str, image_paths: List[str]) -> bool:
    """Insert image records for a story"""
    try:
        images_data = [
            {
                "story_id": story_id,
                "user_id": user_id,
                "storage_path": image_path,
                "sequence_index": index
            }
            for index, image_path in enumerate(image_paths)
        ]
        
        # Insert images in batches
        for i in range(0, len(images_data), 10):
            batch = images_data[i:i+10]
            response = supabase.table("images").insert(batch).execute()
        
        return True
    except Exception as e:
        logger.error(f"Error inserting images: {str(e)}")
        return False


async def get_background_music(music_type: str) -> Dict:
    """Get background music information"""
    try:
        response = supabase.table("background_music").select("*").eq("category", music_type).execute()
        
        if response.data and len(response.data) > 0:
            # Return the first available music of the specified type
            return response.data[0]
        
        # Return default music if type not found
        default_response = supabase.table("background_music").select("*").limit(1).execute()
        if default_response.data and len(default_response.data) > 0:
            return default_response.data[0]
            
        return None
    except Exception as e:
        logger.error(f"Error getting background music: {str(e)}")
        return None