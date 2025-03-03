# api/services/image_service.py
import base64
import os
import uuid
import tempfile
from typing import List, Dict, Tuple, Optional
from io import BytesIO
from PIL import Image
import asyncio
import aiohttp

from transformers import pipeline
from config import settings
from utils.logger import get_logger
from db.supabase import upload_file_to_storage

logger = get_logger("image_service")

# Initialize image-to-text model
image_to_text = None


async def initialize_model():
    """Initialize the image-to-text model"""
    global image_to_text
    
    if image_to_text is None:
        try:
            logger.info("Initializing image-to-text model")
            image_to_text = pipeline(
                "image-to-text", 
                model="Salesforce/blip-image-captioning-base",
                token=settings.HUGGINGFACE_API_TOKEN
            )
            logger.info("Image-to-text model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing image-to-text model: {str(e)}")
            raise e


async def process_base64_image(base64_string: str) -> Tuple[BytesIO, str]:
    """Process base64 encoded image"""
    try:
        # Strip metadata if present (e.g., data:image/jpeg;base64,)
        if ',' in base64_string:
            content_type, base64_data = base64_string.split(',', 1)
            content_type = content_type.split(':')[1].split(';')[0]
        else:
            base64_data = base64_string
            content_type = "image/jpeg"  # Default
        
        # Decode base64
        image_data = base64.b64decode(base64_data)
        
        # Create file-like object
        buffer = BytesIO(image_data)
        
        return buffer, content_type
    except Exception as e:
        logger.error(f"Error processing base64 image: {str(e)}")
        raise e


async def is_url(text: str) -> bool:
    """Check if text is a URL"""
    return text.startswith("http://") or text.startswith("https://")


async def download_image_from_url(url: str) -> BytesIO:
    """Download image from URL"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image, status code: {response.status}")
                
                image_data = await response.read()
                return BytesIO(image_data)
    except Exception as e:
        logger.error(f"Error downloading image from URL: {str(e)}")
        raise e


async def img2text(image_source: str) -> str:
    """Generate text description from image"""
    await initialize_model()
    
    try:
        if await is_url(image_source):
            # Download image from URL
            image_io = await download_image_from_url(image_source)
            image = Image.open(image_io)
        elif image_source.startswith("data:image") or "base64" in image_source:
            # Process base64 image
            image_io, _ = await process_base64_image(image_source)
            image = Image.open(image_io)
        else:
            # Assume it's a file path
            image = Image.open(image_source)
        
        # Generate caption using the model
        result = image_to_text(image)
        
        if result and len(result) > 0:
            return result[0]["generated_text"]
        
        return "An image without a clear description."
    except Exception as e:
        logger.error(f"Error in img2text: {str(e)}")
        return "An image that could not be processed."


async def analyze_multiple_images(image_sources: List[str]) -> List[str]:
    """Analyze multiple images and create detailed scenarios"""
    logger.info(f"Analyzing {len(image_sources)} images")
    
    scenarios = []
    
    for image_source in image_sources:
        try:
            # Generate basic caption
            scenario = await img2text(image_source)
            scenarios.append(scenario)
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            scenarios.append("An image that could not be analyzed.")
    
    return scenarios


async def store_images(user_id: str, image_sources: List[str]) -> List[str]:
    """Store images in Supabase storage and return paths"""
    logger.info(f"Storing {len(image_sources)} images for user {user_id}")
    
    image_paths = []
    
    for idx, image_source in enumerate(image_sources):
        try:
            # Generate a unique file name
            file_name = f"{user_id}_{uuid.uuid4()}.jpg"
            file_path = f"user-uploads/{user_id}/{file_name}"
            
            if await is_url(image_source):
                # Download image from URL
                image_io = await download_image_from_url(image_source)
                image_data = image_io.getvalue()
                content_type = "image/jpeg"
            elif image_source.startswith("data:image") or "base64" in image_source:
                # Process base64 image
                image_io, content_type = await process_base64_image(image_source)
                image_data = image_io.getvalue()
            else:
                # Assume it's already a storage path
                image_paths.append(image_source)
                continue
            
            # Upload to Supabase storage
            file_url = await upload_file_to_storage(
                bucket_name="user-uploads",
                file_data=image_data,
                file_path=file_path,
                content_type=content_type
            )
            
            if file_url:
                image_paths.append(file_path)
            
        except Exception as e:
            logger.error(f"Error storing image: {str(e)}")
    
    return image_paths