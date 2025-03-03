# api/services/music_service.py
import os
import uuid
import tempfile
from typing import Dict, Optional, Tuple
from pydub import AudioSegment
import asyncio

from config import settings
from utils.logger import get_logger
from db.supabase import upload_file_to_storage, get_background_music

logger = get_logger("music_service")


async def download_file(url: str) -> Tuple[bool, Optional[bytes]]:
    """Download a file from URL"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False, None
                
                data = await response.read()
                return True, data
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return False, None


async def download_audio_file(storage_path: str) -> Tuple[bool, Optional[str]]:
    """Download audio file from Supabase storage to local temp file"""
    try:
        # Generate URL
        url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{storage_path}"
        
        # Download file
        success, data = await download_file(url)
        
        if not success or not data:
            return False, None
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name
        
        return True, temp_path
    except Exception as e:
        logger.error(f"Error downloading audio file: {str(e)}")
        return False, None


async def get_music_file(music_type: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """Get music file for specified type"""
    try:
        # Get music info from database
        music_info = await get_background_music(music_type)
        
        if not music_info:
            logger.warning(f"No background music found for type: {music_type}")
            return False, None, None
        
        # Download music file
        storage_path = music_info.get("storage_path")
        
        if not storage_path:
            logger.warning(f"No storage path found for music type: {music_type}")
            return False, None, music_info
        
        success, local_path = await download_audio_file(storage_path)
        
        if not success:
            logger.warning(f"Failed to download music file: {storage_path}")
            return False, None, music_info
        
        return True, local_path, music_info
    except Exception as e:
        logger.error(f"Error getting music file: {str(e)}")
        return False, None, None


async def mix_audio_with_background(
    voice_path: str,
    background_music_type: str,
    user_id: str
) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """Mix voice with background music"""
    try:
        # Download voice audio
        voice_success, voice_local_path = await download_audio_file(voice_path)
        
        if not voice_success:
            return False, "Failed to download voice audio", None
        
        # Get background music
        music_success, music_local_path, music_info = await get_music_file(background_music_type)
        
        if not music_success or not music_local_path:
            # If background music is not available, return voice only
            return True, voice_path, None
        
        # Load audio files with pydub
        voice = AudioSegment.from_file(voice_local_path)
        background = AudioSegment.from_file(music_local_path)
        
        # Ensure background music is long enough
        if len(background) < len(voice):
            # Loop the background music if needed
            times_to_loop = (len(voice) // len(background)) + 1
            background = background * times_to_loop
        
        # Trim background to match voice length
        background = background[:len(voice)]
        
        # Lower the volume of background music
        background = background - 10  # Reduce by 10 dB
        
        # Overlay the tracks
        combined = voice.overlay(background)
        
        # Create output file
        output_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        output_path = output_file.name
        output_file.close()
        
        # Export the final mix
        combined.export(output_path, format="mp3")
        
        # Upload to Supabase storage
        file_name = f"{user_id}_{uuid.uuid4()}.mp3"
        storage_path = f"generated-stories/{user_id}/{file_name}"
        
        with open(output_path, "rb") as f:
            audio_bytes = f.read()
        
        # Upload to storage
        audio_url = await upload_file_to_storage(
            bucket_name="generated-stories",
            file_data=audio_bytes,
            file_path=storage_path,
            content_type="audio/mpeg"
        )
        
        # Clean up temp files
        try:
            os.unlink(voice_local_path)
            os.unlink(music_local_path)
            os.unlink(output_path)
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {str(e)}")
        
        if audio_url:
            return True, storage_path, music_info
        
        return False, "Failed to upload mixed audio", None
        
    except Exception as e:
        logger.error(f"Error mixing audio: {str(e)}")
        return False, str(e), None