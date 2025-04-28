import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
CONTENTFUL_SPACE_ID = os.getenv("CONTENTFUL_SPACE_ID")
CONTENTFUL_ACCESS_TOKEN = os.getenv("CONTENTFUL_ACCESS_TOKEN")

# OpenAI Configuration
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL", "gpt-4.1-2025-04-14"
)  # Using GPT-4.1 2025 model
OPENAI_TEMPERATURE = float(
    os.getenv("OPENAI_TEMPERATURE", "0.7")
)  # Default temperature
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))  # Default max tokens

# Rate Limiting (requests per minute)
RATE_LIMITS = {"openai": 10, "google_maps": 10, "contentful": 10}

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
