import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL", "gpt-5-mini-2025-08-07"
)  # Using the latest GPT-5 model
OPENAI_TEMPERATURE = float(
    os.getenv("OPENAI_TEMPERATURE", "0.4")
)  # Lower for structured JSON output
OPENAI_MAX_TOKENS = int(
    os.getenv("OPENAI_MAX_TOKENS", "3000")
)  # Increased for medium-length articles

# Rate Limiting
RATE_LIMITS = {
    "openai": int(os.getenv("OPENAI_RATE_LIMIT", "3")),  # requests per minute
}

# Retry Configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "1"))  # seconds

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Output Configuration
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(exist_ok=True)
