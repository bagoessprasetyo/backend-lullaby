from dotenv import find_dotenv, load_dotenv
from transformers import pipeline
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import OpenAI
from langchain_mistralai.chat_models import ChatMistralAI
from TTS.api import TTS
import soundfile as sf
import librosa
import os
from pathlib import Path
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import XttsAudioConfig
from TTS.utils.audio import AudioProcessor
from TTS.config.shared_configs import BaseDatasetConfig
from TTS.tts.models.xtts import XttsArgs
from torch.serialization import add_safe_globals
from pydub import AudioSegment
from pydub.effects import speedup, normalize
import torch
from typing import Tuple, Optional
import mimetypes
import logging
from tqdm import tqdm
from functools import lru_cache
import time

load_dotenv(find_dotenv())
HUGGINGFACE_API_TOKEN= os.getenv("HUGGINGFACE_API_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TTSModelCache:
    _instance = None
    _model = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_model(self):
        if self._model is None:
            logger.info("Initializing TTS model (first time only)...")
            self._model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=True,
                gpu=False
            )
        return self._model

def validate_image_file(image_path: str) -> Tuple[bool, str]:
    """Validate image file existence and format."""
    try:
        if not os.path.exists(image_path):
            return False, f"Image file not found: {image_path}"
        
        # Check file extension
        valid_extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']
        if not any(image_path.endswith(ext) for ext in valid_extensions):
            return False, f"Unsupported image format. Please use: {', '.join(valid_extensions)}"
        
        return True, "Image file is valid"
    except Exception as e:
        return False, f"Error validating image file: {str(e)}"

def validate_audio_file(audio_path: str) -> Tuple[bool, str]:
    """Validate audio file existence and format."""
    try:
        if not os.path.exists(audio_path):
            return False, f"Audio file not found: {audio_path}"
        
        # Check file extension
        valid_extensions = ['.wav', '.mp3', '.m4a', '.WAV', '.MP3', '.M4A']
        if not any(audio_path.endswith(ext) for ext in valid_extensions):
            return False, f"Unsupported audio format. Please use: {', '.join(valid_extensions)}"
        
        return True, "Audio file is valid"
    except Exception as e:
        return False, f"Error validating audio file: {str(e)}"

def validate_language(language: str) -> Tuple[bool, str]:
    """Validate language support."""
    if language not in SUPPORTED_LANGUAGES:
        return False, f"Language '{language}' not supported. Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}"
    return True, "Language is supported"

def setup_output_directory() -> Tuple[bool, str]:
    """Setup output directory with proper error handling."""
    try:
        output_dir = os.path.join(os.getcwd(), 'output')
        os.makedirs(output_dir, exist_ok=True)
        return True, output_dir
    except Exception as e:
        return False, f"Failed to create output directory: {str(e)}"

#img2text
def img2text(url):
    image_to_text=pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    text=image_to_text(url)[0]["generated_text"]
    print(text)
    return text

SUPPORTED_LANGUAGES = {
    'en': {
        'name': 'English',
        'prompt_prefix': 'Create an enchanting',
    },
    'id': {
        'name': 'Indonesian',
        'prompt_prefix': 'Buatkan cerita pengantar tidur yang menenangkan',
    },
    'ja': {
        'name': 'Japanese',
        'prompt_prefix': '心温まる子守唄のようなお話を作成してください',
    },
    'fr': {
        'name': 'French',
        'prompt_prefix': 'Créez une histoire apaisante',
    }
}

#story generation
# def generate_story(scenario, language='en'):
    # mistral = ChatMistralAI(
    #     api_key=os.getenv("MISTRAL_API_KEY"),
    #     model="mistral-medium"
    # )
    
    # prefix = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES['en'])['prompt_prefix']

    # prompts = {
    #     'en': f"""{prefix} 10 seconds bedtime story for children based on this scenario: {{scenario}}
        
    #     Story Requirements:
    #     - Theme: Magical and soothing adventure
    #     - Length: Approximately 10 seconds when read aloud (around 25-50 words)
    #     - Structure: Beginning, middle (with gentle adventure), and peaceful ending
    #     - Tone: Warm, gentle, and comforting
        
    #     Please include:
    #     - A main character from the image
    #     - Gentle repetitive elements
    #     - Soft, calming descriptions
    #     - Moments where children can take deep, relaxing breaths
    #     - A peaceful resolution that helps transition to sleep""",
        
    #     'id': f"""{prefix} selama 30 detik berdasarkan skenario ini: {{scenario}}
        
    #     Persyaratan Cerita:
    #     - Tema: Petualangan magis dan menenangkan
    #     - Panjang: Sekitar 30 detik ketika dibacakan (sekitar 100-200 kata)
    #     - Struktur: Awal, tengah (dengan petualangan lembut), dan akhir yang damai
    #     - Nada: Hangat, lembut, dan menenangkan
    #     - Buatkan cerita dengan bahasa indonesia
        
    #     Harap sertakan:
    #     - Karakter utama dari gambar
    #     - Elemen pengulangan yang lembut
    #     - Deskripsi yang menenangkan
    #     - Momen di mana anak-anak bisa mengambil nafas dalam yang menenangkan
    #     - Resolusi damai yang membantu transisi ke tidur""",
        
    #     'ja': f"""{prefix}: {{scenario}}
        
    #     必要な要素:
    #     - テーマ: 魔法のような穏やかな冒険
    #     - 長さ: 読み上げ時約30秒 (100-200語程度)
    #     - 構成: 始まり、中間(穏やかな冒険)、平和な終わり
    #     - トーン: 温かく、優しく、心地よい
        
    #     含めるべき要素:
    #     - 画像からのメインキャラクター
    #     - 優しい繰り返しの要素
    #     - 穏やかな描写
    #     - 子供たちがゆっくりと深呼吸できる場面
    #     - 睡眠への移行を助ける平和な結末""",
        
    #     'fr': f"""{prefix} de 30 secondes pour les enfants basée sur ce scénario: {{scenario}}
        
    #     Exigences de l'histoire:
    #     - Thème: Aventure magique et apaisante
    #     - Durée: Environ 30 secondes à la lecture (environ 100-200 mots)
    #     - Structure: Début, milieu (avec une douce aventure), et fin paisible
    #     - Ton: Chaleureux, doux et réconfortant
        
    #     Veuillez inclure:
    #     - Un personnage principal de l'image
    #     - Des éléments répétitifs doux
    #     - Des descriptions apaisantes
    #     - Des moments où les enfants peuvent prendre des respirations profondes et relaxantes
    #     - Une résolution paisible qui aide à la transition vers le sommeil"""
    # }

    # story_prompt = PromptTemplate(
    #     input_variables=["scenario"],
    #     template=prompts.get(language, prompts['en'])
    # )

    # story_prompt = PromptTemplate(
    #     input_variables=["scenario"],
    #     template="""Create an enchanting 30 seconds bedtime story for children based on this scenario: {scenario}
        
    #     Story Requirements:
    #     - Theme: Magical and soothing adventure
    #     - Length: Approximately 30 seconds when read aloud (around 50-100 words)
    #     - Structure: Beginning, middle (with gentle adventure), and peaceful ending
    #     - Tone: Warm, gentle, and comforting
        
    #     Please include:
    #     - A main character from the image
    #     - Gentle repetitive elements
    #     - Soft, calming descriptions
    #     - Moments where children can take deep, relaxing breaths
    #     - A peaceful resolution that helps transition to sleep"""
    # )
    
    # Create the chain using the new syntax
    # chain = story_prompt | mistral
    
    # Generate the story
    # story = chain.invoke({"scenario": scenario})
    
    # Extract the content from the response
    # if hasattr(story, 'content'):
    #     return story.content
    # return str(story)

def generate_combined_story(scenarios: list, actor_names: list = None, language='en'):
    """Generate a story with custom actor names."""
    
    # Default names if none provided
    if not actor_names:
        actor_names = ["the little one", "the gentle friend", "the kind guardian"]
    
    # Define transition types
    TRANSITIONS = {
        'time': [
            "As the sun began to set...",
            "Later that evening...",
            "Just then...",
            "A few moments later...",
            "As time gently passed...",
            "While the stars began to twinkle..."
        ],
        'movement': [
            "Walking along the path...",
            "Floating gently through the air...",
            "Dancing through the scene...",
            "Drifting peacefully...",
            "Gliding softly forward..."
        ],
        'magic': [
            "In a sparkle of stardust...",
            "With a wave of gentle magic...",
            "Like a dream shifting softly...",
            "As if by magical whispers...",
            "Through a shimmer of moonlight..."
        ],
        'emotion': [
            "Feeling peaceful and calm...",
            "With growing wonder...",
            "Wrapped in warmth and comfort...",
            "Sharing a gentle smile...",
            "With hearts full of joy..."
        ]
    }

    mistral = ChatMistralAI(
        api_key=os.getenv("MISTRAL_API_KEY"),
        model="mistral-medium"
    )
    
    prefix = SUPPORTED_LANGUAGES.get(language, SUPPORTED_LANGUAGES['en'])['prompt_prefix']
    
    # Create scene descriptions with actor names
    scene_prompts = []
    for i, scenario in enumerate(scenarios):
        actor = actor_names[i % len(actor_names)]  # Cycle through names if more scenes than names
        if i > 0:
            transitions = "\n".join([
                f"- {type_}: {', '.join(phrases[:2])}"
                for type_, phrases in TRANSITIONS.items()
            ])
            scene_prompts.append(f"\nPossible transitions to next scene:\n{transitions}\n")
        scene_prompts.append(f"Scene {i+1} with {actor}: {scenario}")

    # Enhanced prompt including actor names
    scene_connection_prompt = PromptTemplate(
        input_variables=["scenes", "actors"],
        template=f"""{prefix} bedtime story for children featuring these characters: {{actors}}

Scenes to connect:
{{scenes}}

Story Requirements:
- Theme: Magical and soothing adventure flowing naturally between scenes
- Length: Approximately 1 minutes when read aloud
- Structure: Create a flowing narrative with gentle transitions between scenes
- Characters: Use the provided character names naturally in the story

Scene Connection Guidelines:
1. Feature the named characters prominently in their scenes
2. Use natural transitions between scenes
3. Create meaningful interactions between characters
4. Maintain continuity in mood and atmosphere
5. Include peaceful pauses between scene transitions

Elements to Include:
- Each character's unique personality
- Gentle interactions between characters
- Soft sounds and sensory details
- Calming actions and movements
- Soothing repetitive elements
- Relaxing breathing moments
- Gradual transition to sleepiness

Make the story progressively more calming, leading to a peaceful conclusion."""
    )
    
    chain = scene_connection_prompt | mistral
    story = chain.invoke({
        "scenes": "\n".join(scene_prompts),
        "actors": ", ".join(actor_names)
    })
    
    if hasattr(story, 'content'):
        return story.content
    return str(story)

def analyze_multiple_images(image_paths: list) -> list:
    """Analyze multiple images and create detailed scenarios."""
    logger.info(f"Analyzing {len(image_paths)} images...")
    scenarios = []

    mistral = ChatMistralAI(
        api_key=os.getenv("MISTRAL_API_KEY"),
        model="mistral-medium"
    )
    
    with tqdm(total=len(image_paths), desc="Analyzing images") as pbar:
        for i, image_path in enumerate(image_paths):
            try:
                base_scenario = img2text(image_path)
                
                # Enhanced scenario prompt
                enhancement_prompt = PromptTemplate(
                    input_variables=["scenario"],
                    template="""Enhance this scene description with soothing details:
                    {scenario}
                    
                    Please include:
                    - Visual details (colors, lights, textures)
                    - Peaceful sounds or silence
                    - Gentle movements
                    - Calming atmosphere
                    - Emotional warmth
                    Keep the description soft and soothing."""
                )
                
                # Enhance the scenario
                chain = enhancement_prompt | mistral
                enhanced = chain.invoke({"scenario": base_scenario})
                
                if hasattr(enhanced, 'content'):
                    scenarios.append(enhanced.content)
                else:
                    scenarios.append(base_scenario)
                    
                pbar.update(1)
            except Exception as e:
                logger.error(f"Error analyzing image {image_path}: {str(e)}")
                scenarios.append(base_scenario)  # Use basic scenario if enhancement fails
                
    return scenarios
# def convert_to_wav(input_file, output_file='reference_voice.wav'):
#     try:
#         # Load the audio file
#         audio, sr = librosa.load(input_file)
        
#         # Save as WAV
#         sf.write(output_file, audio, sr)
#         return output_file
#     except Exception as e:
#         print(f"Error converting audio: {e}")
#         return None

def add_background_music(voice_path, music_path='background.mp3', output_path='final_mix.wav'):
    try:
        print("\nMixing voice with background music...")
        
        # Load the audio files
        voice = AudioSegment.from_wav(voice_path)
        background = AudioSegment.from_file(music_path)
        
        # Ensure background music is long enough
        if len(background) < len(voice):
            # Loop the background music if needed
            times_to_loop = (len(voice) // len(background)) + 1
            background = background * times_to_loop
        
        # Trim background to match voice length
        background = background[:len(voice)]
        
        # Lower the volume of background music (adjust -20 to your preference)
        background = background - 10
        
        # Overlay the tracks
        combined = voice.overlay(background)
        
        # Export the final mix
        combined.export(output_path, format='wav')
        
        print(f"Final audio with music saved to: {output_path}")
        return True, output_path
        
    except Exception as e:
        print(f"Error mixing audio: {e}")
        return False, None

def generate_multi_image_lullaby(
    image_paths: list,
    actor_names: list = None,
    reference_voice_path: str = None,
    language: str = 'en',
    background_music_path: str = 'background.mp3'
) -> tuple:
    """Generate a single lullaby from multiple images with custom actor names."""
    try:
        logger.info("Starting Multi-Image Lullaby Generation...")
        
        # Validate all inputs first
        for image_path in image_paths:
            valid, msg = validate_image_file(image_path)
            if not valid:
                logger.error(msg)
                return None, msg
        
        voice_valid, voice_msg = validate_audio_file(reference_voice_path)
        if not voice_valid:
            logger.error(voice_msg)
            return None, voice_msg
        
        if background_music_path:
            music_valid, music_msg = validate_audio_file(background_music_path)
            if not music_valid:
                logger.error(music_msg)
                return None, music_msg
        
        # 1. Analyze all images
        combined_scenario = analyze_multiple_images(image_paths)
        
        # 2. Generate combined story
        logger.info("Generating combined story...")
        story = generate_combined_story(combined_scenario, actor_names, language)
        
        # 3. Convert to speech
        logger.info("Converting to speech...")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        speech_output = f'combined_story_{timestamp}.wav'
        
        success, message = text_to_speech(
            text=story,
            output_path=speech_output,
            reference_voice=reference_voice_path,
            language=language
        )
        
        if success:
            # 4. Add background music
            logger.info("Adding background music...")
            voice_path = os.path.join('output', speech_output)
            final_output = os.path.join('output', f'final_mix_{timestamp}.wav')
            
            mix_success, final_path = add_background_music(
                voice_path=voice_path,
                music_path=background_music_path,
                output_path=final_output
            )
            
            if mix_success:
                return story, final_path
        
        return story, message
        
    except Exception as e:
        logger.error(f"Error in multi-image lullaby generation: {str(e)}")
        return None, str(e)
# def text_to_speech(text, output_path='final_story.wav', reference_voice='reference_voice.wav'):
    try:
        # Add ALL required configs to safe globals
        add_safe_globals([
            XttsConfig,
            XttsAudioConfig,
            AudioProcessor,
            BaseDatasetConfig,
            XttsArgs  # Add this class
        ])
        
        # Create absolute paths for output
        current_dir = os.getcwd()
        output_dir = os.path.join(current_dir, 'output')
        full_output_path = os.path.join(output_dir, output_path)
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nCreating audio file in: {full_output_path}")
        print(f"Using reference voice from: {reference_voice}")
        
        # Initialize TTS with context manager
        with torch.serialization.safe_globals([BaseDatasetConfig, XttsArgs]):
            tts = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2", 
                progress_bar=True,
                gpu=False
            )
            print("\nGenerating audio...")
            # Generate speech
            tts.tts_to_file(
                text=text,
                file_path=full_output_path,
                speaker_wav=reference_voice,
                language="en",
                speed=0.85
            )
        
        if os.path.exists(full_output_path):
            print(f"\nAudio file successfully created at:\n{full_output_path}")
            return True, f"Successfully generated audio at {full_output_path}"
        else:
            print("\nError: File was not created!")
            return False, "File was not created"
            
    except Exception as e:
        print(f"\nError in text_to_speech: {str(e)}")
        return False, f"Error generating speech: {str(e)}"
# def text_to_speech(text, output_path='final_story.wav', reference_voice='reference_voice.wav', language='en'):
    try:
        # Add ALL required configs to safe globals
        add_safe_globals([
            XttsConfig,
            XttsAudioConfig,
            AudioProcessor,
            BaseDatasetConfig,
            XttsArgs
        ])
        
        # Create absolute paths for output
        current_dir = os.getcwd()
        output_dir = os.path.join(current_dir, 'output')
        full_output_path = os.path.join(output_dir, output_path)
        # full_output_path = output_dir
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nCreating audio file in: {full_output_path}")
        print(f"Using reference voice from: {reference_voice}")
        print(f"Language: {SUPPORTED_LANGUAGES[language]['name']}")
        
        # Initialize TTS with context manager
        with torch.serialization.safe_globals([BaseDatasetConfig, XttsArgs]):
            tts = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2", 
                progress_bar=True,
                gpu=False
            )
            # Fixed indentation here
            print("\nGenerating audio...")
            # Generate speech
            tts.tts_to_file(
                text=text,
                file_path=full_output_path,
                speaker_wav=reference_voice,
                language=language,
                speed=0.75
            )
        
        if os.path.exists(full_output_path):
            print(f"\nAudio file successfully created at:\n{full_output_path}")
            return True, f"Successfully generated audio at {full_output_path}"
        else:
            print("\nError: File was not created!")
            return False, "File was not created"
            
    except Exception as e:
        print(f"\nError in text_to_speech: {str(e)}")
        return False, f"Error generating speech: {str(e)}"
def text_to_speech(text, output_path='final_story.wav', reference_voice='reference_voice.wav', language='en'):
    try:
        add_safe_globals([
            XttsConfig,
            XttsAudioConfig,
            AudioProcessor,
            BaseDatasetConfig,
            XttsArgs
        ])
        
        current_dir = os.getcwd()
        output_dir = os.path.join(current_dir, 'output')
        full_output_path = os.path.join(output_dir, output_path)
        
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nCreating audio file in: {full_output_path}")
        print(f"Using reference voice from: {reference_voice}")
        
        # Use cached model
        with torch.serialization.safe_globals([BaseDatasetConfig, XttsArgs]):
            tts = TTSModelCache.get_instance().get_model()
            
            with tqdm(total=100, desc="Generating audio") as pbar:
                pbar.update(10)  # Model loaded
                
                tts.tts_to_file(
                    text=text,
                    file_path=full_output_path,
                    speaker_wav=reference_voice,
                    language=language,
                    speed=0.75
                )
                pbar.update(90)  # Audio generated
        
        if os.path.exists(full_output_path):
            return True, full_output_path
        else:
            return False, "File was not created"
            
    except Exception as e:
        return False, f"Error generating speech: {str(e)}"

# def generate_lullaby(
#     image_path: str, 
#     reference_voice_path: str, 
#     language: str = 'en', 
#     background_music_path: str = 'background.mp3'
# ) -> Tuple[Optional[str], Optional[str]]:
    """Generate lullaby with comprehensive error handling."""
    try:
        logger.info("Starting Lullaby Generation...")
        
        # Validate inputs
        image_valid, image_msg = validate_image_file(image_path)
        if not image_valid:
            logger.error(image_msg)
            return None, image_msg
            
        voice_valid, voice_msg = validate_audio_file(reference_voice_path)
        if not voice_valid:
            logger.error(voice_msg)
            return None, voice_msg
            
        if background_music_path:
            music_valid, music_msg = validate_audio_file(background_music_path)
            if not music_valid:
                logger.error(music_msg)
                return None, music_msg
                
        lang_valid, lang_msg = validate_language(language)
        if not lang_valid:
            logger.error(lang_msg)
            return None, lang_msg
            
        # Setup output directory
        setup_success, output_dir = setup_output_directory()
        if not setup_success:
            logger.error(output_dir)
            return None, output_dir

        # Process image
        logger.info("Analyzing image...")
        try:
            scenario = img2text(image_path)
        except Exception as e:
            logger.error(f"Failed to analyze image: {str(e)}")
            return None, f"Image analysis failed: {str(e)}"

        # Generate story
        logger.info("Generating story...")
        try:
            story = generate_story(scenario, language)
        except Exception as e:
            logger.error(f"Failed to generate story: {str(e)}")
            return None, f"Story generation failed: {str(e)}"

        # Convert to speech
        logger.info("Converting to speech...")
        speech_output = os.path.join(output_dir, 'story_voice.wav')
        try:
            success, message = text_to_speech(
                text=story,
                output_path='story_voice.wav',
                reference_voice=reference_voice_path,
                language=language
            )
            if not success:
                logger.error(f"Text-to-speech failed: {message}")
                return story, message
        except Exception as e:
            logger.error(f"Text-to-speech failed: {str(e)}")
            return story, f"Text-to-speech failed: {str(e)}"

        # Add background music
        if success and background_music_path:
            logger.info("Adding background music...")
            voice_path = os.path.join(output_dir, 'story_voice.wav')
            final_output = os.path.join(output_dir, 'final_mix.wav')
            
            try:
                mix_success, final_path = add_background_music(
                    voice_path=voice_path,
                    music_path=background_music_path,
                    output_path=final_output
                )
                if mix_success:
                    return story, final_path
                else:
                    logger.error("Failed to add background music")
                    return story, voice_path
            except Exception as e:
                logger.error(f"Failed to add background music: {str(e)}")
                return story, voice_path

        return story, speech_output

    except Exception as e:
        logger.error(f"Unexpected error in generate_lullaby: {str(e)}")
        return None, f"Generation failed: {str(e)}"

# def batch_generate_lullabies(image_paths, reference_voice_path, language='en', background_music_path='background.mp3'):
    """
    Generate multiple lullabies from a list of images
    """
    results = []
    
    logger.info(f"Starting batch processing of {len(image_paths)} images...")
    
    with tqdm(total=len(image_paths), desc="Processing stories") as pbar:
        for idx, image_path in enumerate(image_paths):
            try:
                # Create unique output names
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                story_output = f'story_voice_{idx}_{timestamp}.wav'
                final_output = f'final_mix_{idx}_{timestamp}.wav'
                
                story, audio_file = generate_lullaby(
                    image_path=image_path,
                    reference_voice_path=reference_voice_path,
                    language=language,
                    background_music_path=background_music_path
                )
                
                results.append({
                    'image': image_path,
                    'story': story,
                    'audio': audio_file,
                    'status': 'success' if audio_file else 'failed'
                })
                
            except Exception as e:
                results.append({
                    'image': image_path,
                    'story': None,
                    'audio': None,
                    'status': f'failed: {str(e)}'
                })
            
            pbar.update(1)
            
    return results

# Test script
if __name__ == "__main__":
    try:
        # List of image paths
        IMAGE_PATHS = [
            "bear.jpeg"
        ]
        ACTOR_NAMES = [
            "The Sleepy Bear",
            "The Gentle Owl",
            "The Daring Eagle"
        ]
        VOICE_PATH = "reference_voice.wav"
        BACKGROUND_PATH = "background.mp3"
        LANGUAGE = "en"
        
        story, audio_file = generate_multi_image_lullaby(
            image_paths=IMAGE_PATHS,
            actor_names=ACTOR_NAMES,
            reference_voice_path=VOICE_PATH,
            language=LANGUAGE,
            background_music_path=BACKGROUND_PATH
        )
        
        if story and audio_file:
            print("\nMulti-Image Story generated successfully!")
            print("\nFeaturing:", ", ".join(ACTOR_NAMES))
            print("\nGenerated Story:")
            print(story)
            print(f"\nAudio saved to: {audio_file}")
        else:
            print("\nFailed to generate multi-image story")
            print(f"Error: {audio_file}")
            
    except Exception as e:
        logger.error(f"Program execution failed: {str(e)}")