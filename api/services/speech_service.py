# api/services/speech_service.py
import os
import uuid
import aiohttp
import asyncio
from typing import Dict, Optional, Tuple
import tempfile
from elevenlabs import generate, set_api_key, save

from config import settings
from utils.logger import get_logger
from db.supabase import upload_file_to_storage

logger = get_logger("speech_service")

# Set ElevenLabs API key
set_api_key(settings.ELEVENLABS_API_KEY)


async def generate_speech_async(
    text: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_v2",
    optimize_streaming_latency: int = 2
) -> Tuple[bool, bytes]:
    """Generate speech using ElevenLabs API asynchronously"""
    try:
        # Set settings for the voice
        voice_settings = {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
        
        # Use elevenlabs library to generate audio
        audio = generate(
            text=text,
            voice=voice_id,
            model=model_id,
            optimize_streaming_latency=optimize_streaming_latency,
            voice_settings=voice_settings
        )
        
        return True, audio
        
    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        return False, None


async def generate_and_save_speech(
    text: str, 
    voice_id: str, 
    user_id: str
) -> Tuple[bool, Optional[str]]:
    """Generate speech and save to storage"""
    try:
        # Generate unique file name
        file_name = f"{user_id}_{uuid.uuid4()}.mp3"
        file_path = f"generated-stories/{user_id}/{file_name}"
        
        # Generate speech
        success, audio_data = await generate_speech_async(text, voice_id)
        
        if not success or not audio_data:
            return False, "Failed to generate speech"
        
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            if isinstance(audio_data, bytes):
                temp_file.write(audio_data)
            else:
                # If audio_data is a generator or other format, handle it accordingly
                save(audio_data, temp_file.name)
            
            temp_path = temp_file.name
        
        # Read the temporary file
        with open(temp_path, "rb") as f:
            audio_bytes = f.read()
        
        # Delete temporary file
        os.unlink(temp_path)
        
        # Upload to Supabase storage
        audio_url = await upload_file_to_storage(
            bucket_name="generated-stories",
            file_data=audio_bytes,
            file_path=file_path,
            content_type="audio/mpeg"
        )
        
        if audio_url:
            return True, file_path
        
        return False, "Failed to upload audio file"
        
    except Exception as e:
        logger.error(f"Error in generate_and_save_speech: {str(e)}")
        return False, str(e)


async def get_voice_id(voice_preference: str) -> str:
    """Get voice ID based on preference"""
    # If it's already a valid ElevenLabs voice ID, use it directly
    if len(voice_preference) > 10 and not voice_preference.startswith("ai-"):
        return voice_preference
    
    # Otherwise, use one of our predefined voices
    return settings.DEFAULT_VOICES.get(voice_preference, settings.DEFAULT_VOICES["ai-1"])