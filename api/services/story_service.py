# api/services/story_service.py
import random
import httpx
from typing import List, Dict, Tuple, Optional, Any
import asyncio
import aiohttp

from config import settings
from utils.logger import get_logger
from models.story import DurationEnum, LanguageEnum, ThemeEnum

logger = get_logger("story_service")

# Supported language configurations
LANGUAGE_CONFIG = {
    "english": {
        "name": "English",
        "prompt_prefix": "Create an enchanting",
        "iso": "en"
    },
    "indonesian": {
        "name": "Indonesian",
        "prompt_prefix": "Buatkan cerita pengantar tidur yang menenangkan",
        "iso": "id"
    },
    "japanese": {
        "name": "Japanese",
        "prompt_prefix": "心温まる子守唄のようなお話を作成してください",
        "iso": "ja"
    },
    "french": {
        "name": "French",
        "prompt_prefix": "Créez une histoire apaisante",
        "iso": "fr"
    }
}

# Duration mappings
DURATION_CONFIG = {
    "short": {
        "words": settings.DURATION_SHORT_WORDS,
        "time_seconds": 60,
        "description": "approximately 1 minute when read aloud"
    },
    "medium": {
        "words": settings.DURATION_MEDIUM_WORDS,
        "time_seconds": 180,
        "description": "approximately 3 minutes when read aloud"
    },
    "long": {
        "words": settings.DURATION_LONG_WORDS,
        "time_seconds": 300,
        "description": "approximately 5 minutes when read aloud"
    }
}

# Theme descriptions
THEME_DESCRIPTIONS = {
    "adventure": "exciting journey with discovery and wonder",
    "fantasy": "magical realm with enchanted elements",
    "bedtime": "calming narrative designed for peaceful sleep",
    "educational": "entertaining story with valuable lessons",
    "customized": "unique narrative tailored to the provided images"
}


async def generate_title(
    scenarios: List[str], 
    theme: str, 
    language: str
) -> str:
    """Generate an appropriate title for the story"""
    try:
        # Prepare prompt for title generation
        scenario_text = "\n".join(scenarios)
        language_config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["english"])
        
        prompt = f"""Create a short, engaging title for a children's bedtime story based on these scene descriptions:
{scenario_text}

The story theme is: {THEME_DESCRIPTIONS.get(theme, "a magical adventure")}
The title should be in {language_config["name"]}.
Title should be captivating and no more than 6 words.
"""

        # Use OpenAI API for title generation
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are a creative children's book title creator."},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 30,
                    "temperature": 0.7
                },
                timeout=10.0
            )
            
            if response.status_code == 200:
                result = response.json()
                title = result["choices"][0]["message"]["content"].strip().strip('"')
                return title
            
            # Fallback if API call fails
            return generate_fallback_title(scenarios, theme, language)
            
    except Exception as e:
        logger.error(f"Error generating title: {str(e)}")
        return generate_fallback_title(scenarios, theme, language)


def generate_fallback_title(scenarios: List[str], theme: str, language: str) -> str:
    """Generate a fallback title if API call fails"""
    adjectives = {
        "english": ["Magical", "Dreamy", "Wonderful", "Enchanted", "Sleepy", "Cozy", "Starry"],
        "french": ["Magique", "Rêveur", "Merveilleux", "Enchanté", "Somnolent", "Confortable", "Étoilé"],
        "japanese": ["魔法の", "夢見る", "素晴らしい", "魅惑的な", "眠たい", "居心地の良い", "星空の"],
        "indonesian": ["Ajaib", "Bermimpi", "Indah", "Mempesona", "Mengantuk", "Nyaman", "Berbintang"]
    }
    
    nouns = {
        "english": ["Adventure", "Journey", "Dreams", "Night", "Forest", "Friends", "Story"],
        "french": ["Aventure", "Voyage", "Rêves", "Nuit", "Forêt", "Amis", "Histoire"],
        "japanese": ["冒険", "旅", "夢", "夜", "森", "友達", "物語"],
        "indonesian": ["Petualangan", "Perjalanan", "Mimpi", "Malam", "Hutan", "Teman", "Cerita"]
    }
    
    lang = language if language in adjectives else "english"
    
    adj = random.choice(adjectives[lang])
    noun = random.choice(nouns[lang])
    
    return f"{adj} {noun}"


async def generate_story_from_scenarios(
    scenarios: List[str],
    characters: List[Dict],
    theme: str,
    duration: str,
    language: str
) -> Tuple[str, int]:
    """Generate a complete story from image scenarios"""
    try:
        # Prepare character names
        character_names = [char["name"] for char in characters if char["name"]]
        if not character_names:
            character_names = ["the child", "the little one", "the dreamer"]
        
        # Create scene descriptions with character names
        scene_prompts = []
        for i, scenario in enumerate(scenarios):
            char_name = character_names[i % len(character_names)]
            scene_prompts.append(f"Scene {i+1} with {char_name}: {scenario}")
        
        # Get language configuration
        language_config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["english"])
        
        # Get duration configuration
        duration_config = DURATION_CONFIG.get(duration, DURATION_CONFIG["medium"])
        
        # Build complete prompt
        prompt = f"""{language_config["prompt_prefix"]} bedtime story for children featuring these characters: {', '.join(character_names)}

Scenes to include:
{chr(10).join(scene_prompts)}

Story Requirements:
- Theme: {THEME_DESCRIPTIONS.get(theme, "a magical adventure")}
- Length: {duration_config["description"]} (around {duration_config["words"]} words)
- Structure: Create a flowing narrative with gentle transitions between scenes
- Characters: Use the provided character names naturally in the story
- Language: Write in {language_config["name"]}

Story should:
- Be soothing and calming, perfect for bedtime reading
- Feature the named characters prominently in their scenes
- Create meaningful interactions between characters
- Include peaceful pauses between scene transitions
- Have a peaceful conclusion

Elements to Include:
- Each character's unique personality
- Gentle interactions between characters
- Soft sounds and sensory details
- Calming actions and movements
- Soothing repetitive elements
- Relaxing breathing moments
- Gradual transition to sleepiness

Make the story progressively more calming, leading to a peaceful conclusion."""

        # Use OpenAI API for story generation (better multilingual support)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "system", 
                            "content": f"You are a professional children's story writer specializing in soothing bedtime stories in {language_config['name']}."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.7
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                story_text = result["choices"][0]["message"]["content"].strip()
                
                # Calculate approximate duration in seconds
                word_count = len(story_text.split())
                
                # Estimate duration as a proportion of the target word count
                duration_ratio = word_count / duration_config["words"]
                estimated_duration_seconds = int(duration_config["time_seconds"] * duration_ratio)
                
                return story_text, estimated_duration_seconds
            
            # If API call fails, raise exception
            raise Exception(f"Failed to generate story: {response.text}")
            
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        raise e