# api/utils/env_validator.py
"""
Environment variable validator to ensure all required variables are set
"""
import os
import sys
from typing import Dict, List, Any, Optional

# Define required environment variables and their descriptions
REQUIRED_VARS = {
    "SUPABASE_URL": "Supabase project URL",
    "SUPABASE_KEY": "Supabase anon key for client-side operations",
    "SUPABASE_SERVICE_ROLE_KEY": "Supabase service role key for admin operations",
    "ELEVENLABS_API_KEY": "ElevenLabs API key for text-to-speech",
    "HUGGINGFACE_API_TOKEN": "Hugging Face API token for ML models",
    "OPENAI_API_KEY": "OpenAI API key for story generation",
    "SECRET_KEY": "Secret key for JWT encryption",
}

# Define optional environment variables with defaults
OPTIONAL_VARS = {
    "PORT": {"default": "8000", "description": "Port to run the API server on"},
    "ENVIRONMENT": {"default": "development", "description": "Environment (development, staging, production)"},
    "LOG_LEVEL": {"default": "INFO", "description": "Logging level"},
    "CORS_ORIGINS": {"default": "*", "description": "Allowed CORS origins (comma-separated)"},
}

# Variables only required in production
PRODUCTION_ONLY_VARS = [
    "SENTRY_DSN",
    "REDIS_URL"
]


def validate_environment(env: Dict[str, Any] = None, is_production: bool = False) -> List[str]:
    """
    Validate environment variables
    
    Args:
        env: Dictionary of environment variables (defaults to os.environ)
        is_production: Whether to enforce production-only variables
        
    Returns:
        List of error messages, empty if all required variables are set
    """
    if env is None:
        env = os.environ
    
    errors = []
    
    # Check required variables
    for var_name, description in REQUIRED_VARS.items():
        if var_name not in env or not env[var_name]:
            errors.append(f"Missing required environment variable: {var_name} ({description})")
    
    # Check production-only variables
    if is_production:
        for var_name in PRODUCTION_ONLY_VARS:
            if var_name not in env or not env[var_name]:
                errors.append(f"Missing production-required environment variable: {var_name}")
    
    return errors


def check_and_warn(exit_on_error: bool = False) -> None:
    """
    Check environment variables and print warnings or exit
    
    Args:
        exit_on_error: Whether to exit the process if errors are found
    """
    # Determine if we're in production
    is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
    
    # Validate environment
    errors = validate_environment(is_production=is_production)
    
    if errors:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"  - {error}")
        
        if exit_on_error:
            print("Exiting due to missing required environment variables.")
            sys.exit(1)
        else:
            print("Warning: Continuing despite missing environment variables.")
    else:
        environment = "PRODUCTION" if is_production else "DEVELOPMENT"
        print(f"✅ Environment validation successful (mode: {environment}).")


def load_defaults() -> None:
    """Load default values for optional environment variables"""
    for var_name, config in OPTIONAL_VARS.items():
        if var_name not in os.environ or not os.environ[var_name]:
            os.environ[var_name] = config["default"]

if __name__ == "__main__":
    # Run validation if script is executed directly
    check_and_warn(exit_on_error=True)