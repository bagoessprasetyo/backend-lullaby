# api/db/repositories/user_repository.py
from typing import Dict, List, Optional, Tuple, Any
import uuid
import asyncio
from datetime import datetime

from db.supabase import supabase, supabase_admin
from utils.logger import get_logger

logger = get_logger("user_repository")

class UserRepository:
    """Repository for user-related database operations"""
    
    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[Dict]:
        """Get a user by ID"""
        try:
            response = supabase.table("profiles").select("*").eq("id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_by_oauth_id(oauth_id: str) -> Optional[Dict]:
        """Get a user by OAuth ID"""
        try:
            response = supabase.table("profiles").select("*").eq("oauth_id", oauth_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error getting user by OAuth ID: {str(e)}")
            return None
    
    @staticmethod
    async def create_or_update_user(
        oauth_id: str,
        email: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Optional[Dict]:
        """Create or update a user profile"""
        try:
            # Check if user exists
            existing_user = await UserRepository.get_user_by_oauth_id(oauth_id)
            
            if existing_user:
                # Update existing user
                response = supabase.table("profiles").update({
                    "email": email,
                    "name": name,
                    "avatar_url": avatar_url,
                    "last_login_at": datetime.now().isoformat()
                }).eq("id", existing_user["id"]).execute()
                
                if response.data and len(response.data) > 0:
                    return response.data[0]
            else:
                # Create new user
                user_data = {
                    "id": str(uuid.uuid4()),
                    "oauth_id": oauth_id,
                    "email": email,
                    "name": name,
                    "avatar_url": avatar_url,
                    "created_at": datetime.now().isoformat(),
                    "last_login_at": datetime.now().isoformat(),
                    "subscription_tier": "free",
                    "subscription_status": "active",
                    "story_credits": 5,  # Default starting credits
                    "voice_credits": 0
                }
                
                response = supabase.table("profiles").insert(user_data).execute()
                
                if response.data and len(response.data) > 0:
                    return response.data[0]
            
            return None
        except Exception as e:
            logger.error(f"Error creating or updating user: {str(e)}")
            return None
    
    @staticmethod
    async def check_user_credits(user_id: str) -> Dict:
        """Check if a user has enough credits to generate a story"""
        try:
            user = await UserRepository.get_user_by_id(user_id)
            
            if not user:
                return {"has_credits": False, "reason": "User not found"}
            
            story_credits = user.get("story_credits", 0)
            
            if story_credits <= 0:
                return {"has_credits": False, "reason": "Insufficient story credits"}
            
            return {
                "has_credits": True,
                "story_credits": story_credits,
                "subscription_tier": user.get("subscription_tier", "free")
            }
        except Exception as e:
            logger.error(f"Error checking user credits: {str(e)}")
            return {"has_credits": False, "reason": str(e)}
    
    @staticmethod
    async def check_subscription_features(user_id: str) -> Dict:
        """Check which features are available based on subscription tier"""
        try:
            user = await UserRepository.get_user_by_id(user_id)
            
            if not user:
                return {"success": False, "reason": "User not found"}
            
            subscription_tier = user.get("subscription_tier", "free")
            
            # Define feature availability based on subscription tier
            features = {
                "long_stories": subscription_tier in ["premium", "family"],
                "background_music": subscription_tier in ["premium", "family"],
                "custom_voices": subscription_tier in ["premium", "family"],
                "educational_themes": subscription_tier in ["premium", "family"],
                "story_sharing": subscription_tier in ["family"],
                "unlimited_storage": subscription_tier in ["premium", "family"],
                "max_images": 5 if subscription_tier in ["premium", "family"] else 3
            }
            
            return {
                "success": True,
                "subscription_tier": subscription_tier,
                "features": features
            }
        except Exception as e:
            logger.error(f"Error checking subscription features: {str(e)}")
            return {"success": False, "reason": str(e)}
    
    @staticmethod
    async def decrement_story_credits(user_id: str) -> bool:
        """Decrement user's story credits"""
        try:
            user = await UserRepository.get_user_by_id(user_id)
            
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
    
    @staticmethod
    async def add_story_credits(user_id: str, credits: int) -> bool:
        """Add story credits to a user"""
        try:
            user = await UserRepository.get_user_by_id(user_id)
            
            if not user:
                return False
            
            current_credits = user.get("story_credits", 0)
            new_credits = current_credits + credits
            
            response = supabase.table("profiles").update({
                "story_credits": new_credits
            }).eq("id", user_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error adding story credits: {str(e)}")
            return False
    
    @staticmethod
    async def update_subscription(user_id: str, tier: str, status: str) -> bool:
        """Update user subscription tier and status"""
        try:
            response = supabase.table("profiles").update({
                "subscription_tier": tier,
                "subscription_status": status,
                "subscription_expiry": datetime.now().isoformat() if status == "cancelled" else None
            }).eq("id", user_id).execute()
            
            # Record subscription event
            event_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "event_type": "changed",
                "new_tier": tier,
                "effective_date": datetime.now().isoformat()
            }
            
            supabase.table("subscription_events").insert(event_data).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            return False
    
    @staticmethod
    async def get_user_preferences(user_id: str) -> Optional[Dict]:
        """Get user preferences"""
        try:
            response = supabase.table("user_preferences").select("*").eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            
            # Create default preferences if not exist
            default_prefs = {
                "user_id": user_id,
                "default_language": "en",
                "default_theme": "adventure",
                "theme_mode": "dark",
                "email_notifications": True,
                "auto_play": False
            }
            
            supabase.table("user_preferences").insert(default_prefs).execute()
            
            return default_prefs
        except Exception as e:
            logger.error(f"Error getting user preferences: {str(e)}")
            return None