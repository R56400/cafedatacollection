import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # To be configured later
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")  # To be configured later
CONTENTFUL_SPACE_ID = os.getenv("CONTENTFUL_SPACE_ID")
CONTENTFUL_ACCESS_TOKEN = os.getenv("CONTENTFUL_ACCESS_TOKEN")

# Rate Limiting (requests per minute)
RATE_LIMITS = {
    "openai": 10,
    "google_maps": 10,
    "contentful": 10
}

# Cache TTL (in seconds)
CACHE_TTL = {
    "api_responses": 86400,  # 24 hours
    "processed_data": 604800,  # 1 week
    "geocoding": 2592000  # 30 days
}

# Retry Configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # Base delay in seconds for exponential backoff

# Logging Configuration
LOG_LEVEL = "INFO"

# Input/Output Configuration
INPUT_ENCODING = "utf-8"
OUTPUT_ENCODING = "utf-8"

# Author Information
AUTHOR_NAME = "Chris Jordan" 