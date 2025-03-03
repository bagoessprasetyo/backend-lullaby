# test_api.py
import os
import base64
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API URL
API_URL = os.getenv("API_URL", "http://localhost:8000")

# User ID for testing
TEST_USER_ID = os.getenv("TEST_USER_ID", "test-user-id")


def encode_image_to_base64(image_path):
    """Encode image to base64"""
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded_string}"


def test_story_generation():
    """Test story generation endpoint"""
    print("Testing story generation endpoint...")
    
    # Encode test images
    image_paths = ["./test_images/image1.jpg", "./test_images/image2.jpg"]
    
    # Check if test images exist
    for path in image_paths:
        if not os.path.exists(path):
            print(f"Error: Test image not found: {path}")
            print("Please add test images to the test_images directory")
            return
    
    images = [encode_image_to_base64(path) for path in image_paths]
    
    # Prepare request payload
    payload = {
        "images": images,
        "characters": [
            {"name": "Sophie", "description": "A curious little girl with a big imagination"},
            {"name": "Max", "description": "Sophie's loyal and adventurous dog"}
        ],
        "theme": "adventure",
        "duration": "short",
        "language": "english",
        "backgroundMusic": "calming",
        "voice": "ai-1",
        "userId": TEST_USER_ID
    }
    
    # Send request
    try:
        response = requests.post(
            f"{API_URL}/api/stories/generate",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {TEST_USER_ID}"
            },
            json=payload,
            timeout=120  # Longer timeout for story generation
        )
        
        # Print response
        print(f"Status Code: {response.status_code}")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        # Check if successful
        if response.status_code == 200 and response.json().get("success"):
            print("\nStory generation successful!")
            
            # Print story details
            data = response.json()
            print(f"Story ID: {data.get('storyId')}")
            print(f"Title: {data.get('title')}")
            print(f"Duration: {data.get('duration')} seconds")
            print(f"Audio URL: {data.get('audioUrl')}")
            
            # Save story text to file
            with open("generated_story.txt", "w") as f:
                f.write(data.get("textContent", ""))
            print("Story text saved to generated_story.txt")
        else:
            print("\nStory generation failed!")
            
    except Exception as e:
        print(f"Error: {str(e)}")


def main():
    """Main function"""
    print("API Testing Script")
    print("=================")
    
    # Create test_images directory if it doesn't exist
    os.makedirs("test_images", exist_ok=True)
    
    # Test health check endpoint
    try:
        response = requests.get(f"{API_URL}/api/health")
        print(f"Health check status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Health check failed: {str(e)}")
    
    # Ask user if they want to test story generation
    choice = input("\nDo you want to test story generation? (y/n): ")
    
    if choice.lower() == "y":
        test_story_generation()
    else:
        print("Skipping story generation test")


if __name__ == "__main__":
    main()