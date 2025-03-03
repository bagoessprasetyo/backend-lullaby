# api/db/repositories/story_repository.py
from typing import Dict, List, Optional, Tuple, Any
import uuid
import asyncio
from datetime import datetime

from db.supabase import supabase, supabase_admin
from utils.logger import get_logger
from config import settings

logger = get_logger("story_repository")

class StoryRepository:
    """Repository for story-related database operations"""
    
    @staticmethod
    async def get_story_by_id(story_id: str, user_id: Optional[str] = None) -> Optional[Dict]:
        """Get a story by ID with optional user verification"""
        try:
            query = supabase.table("stories").select(
                """
                *,
                images(*),
                characters(*),
                story_tags(*)
                """
            ).eq("id", story_id)
            
            # If user_id is provided, verify ownership
            if user_id:
                query = query.eq("user_id", user_id)
                
            response = query.execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error getting story by ID: {str(e)}")
            return None
    
    @staticmethod
    async def get_stories_by_user(
        user_id: str,
        limit: int = 10,
        offset: int = 0,
        filters: Dict = None
    ) -> Tuple[List[Dict], int]:
        """Get stories for a specific user with optional filters"""
        try:
            # Start with base query
            query = supabase.table("stories").select(
                """
                *,
                images!inner(storage_path, sequence_index)
                """,
                count="exact"
            ).eq("user_id", user_id)
            
            # Apply filters if provided
            if filters:
                if "theme" in filters and filters["theme"]:
                    query = query.eq("theme", filters["theme"])
                    
                if "language" in filters and filters["language"]:
                    query = query.eq("language", filters["language"])
                    
                if "is_favorite" in filters and filters["is_favorite"] is not None:
                    query = query.eq("is_favorite", filters["is_favorite"])
                    
                if "search" in filters and filters["search"]:
                    query = query.ilike("title", f"%{filters['search']}%")
                    
                if "created_after" in filters and filters["created_after"]:
                    query = query.gte("created_at", filters["created_after"])
                    
                if "created_before" in filters and filters["created_before"]:
                    query = query.lte("created_at", filters["created_before"])
            
            # Apply ordering
            if filters and "order_by" in filters and filters["order_by"]:
                order_field, order_direction = filters["order_by"].split(":")
                query = query.order(order_field, {"ascending": order_direction == "asc"})
            else:
                # Default ordering: newest first
                query = query.order("created_at", {"ascending": False})
            
            # Apply pagination
            query = query.range(offset, offset + limit - 1)
            
            # Execute query
            response = query.execute()
            
            return response.data or [], response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting stories for user: {str(e)}")
            return [], 0
    
    @staticmethod
    async def create_story(
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
        """Create a new story"""
        try:
            # Prepare story data
            story_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": title,
                "text_content": text_content,
                "language": settings.LANGUAGE_MAP.get(language, "en"),
                "theme": theme,
                "duration": duration,
                "audio_url": audio_url,
                "storage_path": storage_path,
                "background_music_id": background_music_id,
                "created_at": datetime.now().isoformat(),
                "is_favorite": False,
                "play_count": 0
            }
            
            response = supabase.table("stories").insert(story_data).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]["id"]
            
            return None
        except Exception as e:
            logger.error(f"Error creating story: {str(e)}")
            return None
    
    @staticmethod
    async def add_story_characters(story_id: str, characters: List[Dict]) -> bool:
        """Add characters to a story"""
        try:
            if not characters:
                return True
                
            # Prepare character data
            character_data = [
                {
                    "id": str(uuid.uuid4()),
                    "story_id": story_id,
                    "name": character["name"],
                    "description": character.get("description", "")
                }
                for character in characters
            ]
            
            # Insert characters in batches to avoid issues with large lists
            for i in range(0, len(character_data), 10):
                batch = character_data[i:i+10]
                response = supabase.table("characters").insert(batch).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error adding story characters: {str(e)}")
            return False
    
    @staticmethod
    async def add_story_images(story_id: str, user_id: str, image_paths: List[str]) -> bool:
        """Add images to a story"""
        try:
            if not image_paths:
                return True
                
            # Prepare image data
            image_data = [
                {
                    "id": str(uuid.uuid4()),
                    "story_id": story_id,
                    "user_id": user_id,
                    "storage_path": image_path,
                    "sequence_index": index,
                    "upload_date": datetime.now().isoformat()
                }
                for index, image_path in enumerate(image_paths)
            ]
            
            # Insert images in batches
            for i in range(0, len(image_data), 10):
                batch = image_data[i:i+10]
                response = supabase.table("images").insert(batch).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error adding story images: {str(e)}")
            return False
    
    @staticmethod
    async def add_story_tags(story_id: str, tags: List[str]) -> bool:
        """Add tags to a story"""
        try:
            if not tags:
                return True
                
            # Prepare tag data
            tag_data = [
                {
                    "id": str(uuid.uuid4()),
                    "story_id": story_id,
                    "tag": tag.lower().strip()
                }
                for tag in tags
            ]
            
            # Insert tags
            response = supabase.table("story_tags").insert(tag_data).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error adding story tags: {str(e)}")
            return False
    
    @staticmethod
    async def update_story_favorite(story_id: str, user_id: str, is_favorite: bool) -> bool:
        """Update the favorite status of a story"""
        try:
            # Verify ownership
            story = await StoryRepository.get_story_by_id(story_id, user_id)
            
            if not story:
                return False
                
            # Update favorite status
            response = supabase.table("stories").update({
                "is_favorite": is_favorite
            }).eq("id", story_id).eq("user_id", user_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating story favorite status: {str(e)}")
            return False
    
    @staticmethod
    async def increment_play_count(story_id: str) -> bool:
        """Increment the play count for a story"""
        try:
            # Update play count
            response = supabase.table("stories").update({
                "play_count": supabase.rpc("increment", {})
            }).eq("id", story_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error incrementing play count: {str(e)}")
            return False
    
    @staticmethod
    async def record_play_history(
        user_id: str,
        story_id: str,
        completed: bool = False,
        progress_percentage: int = 0
    ) -> Optional[str]:
        """Record play history for a story"""
        try:
            # Prepare play history data
            play_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "story_id": story_id,
                "played_at": datetime.now().isoformat(),
                "completed": completed,
                "progress_percentage": progress_percentage
            }
            
            response = supabase.table("play_history").insert(play_data).execute()
            
            # Also increment play count
            await StoryRepository.increment_play_count(story_id)
            
            if response.data and len(response.data) > 0:
                return response.data[0]["id"]
            
            return None
        except Exception as e:
            logger.error(f"Error recording play history: {str(e)}")
            return None
    
    @staticmethod
    async def delete_story(story_id: str, user_id: str) -> bool:
        """Delete a story"""
        try:
            # Verify ownership
            story = await StoryRepository.get_story_by_id(story_id, user_id)
            
            if not story:
                return False
                
            # Delete story (related records will be cascade deleted)
            response = supabase.table("stories").delete().eq("id", story_id).eq("user_id", user_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting story: {str(e)}")
            return False