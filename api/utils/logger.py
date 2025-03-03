# api/utils/logger.py
import sys
import os
from loguru import logger

# Configure loguru logger
log_level = os.getenv("LOG_LEVEL", "INFO")
log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

# Remove default handler
logger.remove()

# Add console handler
logger.add(
    sys.stderr,
    format=log_format,
    level=log_level,
    colorize=True
)

# Add file handler
logger.add(
    "logs/story_api_{time:YYYY-MM-DD}.log",
    rotation="500 MB",
    retention="10 days",
    format=log_format,
    level=log_level,
    compression="zip"
)

# Create a function to get logger for specific module
def get_logger(name):
    return logger.bind(name=name)