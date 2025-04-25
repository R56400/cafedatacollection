import time
import logging
import os
from typing import Dict, List, Optional
from pathlib import Path
import httpx
import json

from .utils.logging import setup_logger
from .utils.caching import CacheManager
from .config import (
    CACHE_DIR,
    RATE_LIMITS,
    CACHE_TTL,
    MAX_RETRIES,
    RETRY_DELAY,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS
)

# Set logging to DEBUG level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

cache_manager = CacheManager(CACHE_DIR)

class LLMClient:
    def __init__(self):
        """Initialize the LLM client.
        
        Note: Actual API client initialization will be added when API key is available.
        """
        self.api_key = OPENAI_API_KEY
        self.model = OPENAI_MODEL
        self.temperature = OPENAI_TEMPERATURE
        self.max_tokens = OPENAI_MAX_TOKENS
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.last_request_time = 0
        self._load_prompt_templates()
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your .env file.")
        
        # Log initialization details (excluding API key)
        logger.debug(f"Initialized LLMClient with:")
        logger.debug(f"- Model: {self.model}")
        logger.debug(f"- Temperature: {self.temperature}")
        logger.debug(f"- Max tokens: {self.max_tokens}")
        logger.debug(f"- Base URL: {self.base_url}")
        logger.debug(f"- API key present: {'Yes' if self.api_key else 'No'}")
    
    def _load_prompt_templates(self) -> None:
        """Load prompt templates from the templates directory."""
        self.templates = {
            'cafe_search': self._load_template('cafe_search.txt'),
            'cafe_details': self._load_template('cafe_details.txt'),
            'rich_text': self._load_template('rich_text.txt')
        }
    
    def _load_template(self, template_name: str) -> str:
        """Load a specific prompt template.
        
        Args:
            template_name: Name of the template file
        
        Returns:
            Template string or None if file not found
        """
        try:
            template_path = Path(__file__).parent / 'templates' / template_name
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Template not found: {template_name}")
            return None
    
    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed the rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # Convert rate limit to seconds
        min_interval = 60.0 / RATE_LIMITS['openai']
        
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        
        self.last_request_time = time.time()
    
    async def _make_openai_request(self, messages: List[Dict[str, str]]) -> Optional[str]:
        try:
            logger.debug("Preparing OpenAI API request")
            logger.debug(f"Request details: model={self.model}, temperature={self.temperature}, max_tokens={self.max_tokens}")
            logger.debug(f"Messages to send: {json.dumps(messages, indent=2)}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    },
                    timeout=30.0
                )
                
                logger.debug(f"Response status code: {response.status_code}")
                
                if response.status_code == 401:
                    logger.error("OpenAI API key is invalid")
                    raise ValueError("Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env")
                
                response.raise_for_status()
                result = response.json()
                logger.debug(f"Raw API response: {json.dumps(result, indent=2)}")
                
                if "choices" not in result or not result["choices"]:
                    logger.error("No choices in API response")
                    logger.debug(f"Full response: {json.dumps(result, indent=2)}")
                    return None
                    
                logger.info("Successfully received response from OpenAI API")
                return result["choices"][0]["message"]["content"]
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {str(e)}")
            logger.debug(f"Response content: {e.response.text if hasattr(e, 'response') else 'No response content'}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            logger.debug(f"Error type: {type(e).__name__}")
            raise

    async def get_cafes_for_city(self, city: str, num_cafes: int = 5) -> List[Dict]:
        logger.info(f"Getting {num_cafes} cafes for city: {city}")
        
        try:
            with open("cafe_data_collection/templates/cafe_search.txt", "r") as f:
                template = f.read()
            
            messages = [
                {"role": "system", "content": template},
                {"role": "user", "content": f"Find {num_cafes} cafes in {city}"}
            ]
            
            response = await self._make_openai_request(messages)
            if not response:
                logger.error("No response received from OpenAI API")
                return []
            
            try:
                cafes = json.loads(response)
                logger.info(f"Successfully parsed {len(cafes)} cafes from response")
                return cafes
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {response}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting cafes for {city}: {str(e)}")
            raise
    
    async def enrich_cafe_details(self, cafe_info: Dict) -> Dict:
        """Enrich basic cafe information with detailed content.
        
        Args:
            cafe_info: Dictionary containing basic cafe information
        
        Returns:
            Dictionary containing enriched cafe information
        """
        # Check cache first
        cache_key = f"details_{cafe_info['cafeName']}_{cafe_info['city']}"
        cached_result = cache_manager.load('api_responses', cache_key)
        if cached_result:
            return cached_result
            
        try:
            # Get the template
            template = self.templates.get('cafe_details')
            if not template:
                logger.error("Cafe details template not found")
                return cafe_info
                
            # Format the system message with cafe info
            system_content = template.format(
                cafeName=cafe_info['cafeName'],
                city=cafe_info['city'],
                briefDescription=cafe_info['excerpt'],
                cafeAddress=cafe_info['cafeAddress']
            )
            
            # Prepare messages for the API call
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Please provide detailed information about {cafe_info['cafeName']}"}
            ]
            
            # Make the API call
            response = await self._make_openai_request(messages)
            if not response:
                logger.error("No response received from OpenAI API")
                return cafe_info
                
            try:
                # Log the raw response for debugging
                logger.debug(f"Raw response for {cafe_info['cafeName']}: {response}")
                
                # Parse the enriched details
                enriched_details = json.loads(response)
                
                # Validate required fields
                required_fields = [
                    "overallScore", "coffeeScore", "foodScore", "vibeScore",
                    "atmosphereScore", "serviceScore", "valueScore", "excerpt",
                    "vibeDescription", "theStory", "craftExpertise", "setsApart"
                ]
                
                missing_fields = [field for field in required_fields if field not in enriched_details]
                if missing_fields:
                    logger.error(f"Missing required fields for {cafe_info['cafeName']}: {missing_fields}")
                    return cafe_info
                
                # Validate rich text fields
                rich_text_fields = ["vibeDescription", "theStory", "craftExpertise", "setsApart"]
                for field in rich_text_fields:
                    if not isinstance(enriched_details[field], dict) or "nodeType" not in enriched_details[field]:
                        logger.error(f"Invalid rich text format for {field} in {cafe_info['cafeName']}")
                        return cafe_info
                
                # Merge the enriched details with the original cafe info
                cafe_info.update(enriched_details)
                
                # Cache the result
                cache_manager.save('api_responses', cache_key, cafe_info)
                
                return cafe_info
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response for {cafe_info['cafeName']}: {str(e)}")
                logger.error(f"Raw response: {response}")
                return cafe_info
                
        except Exception as e:
            logger.error(f"Error enriching details for {cafe_info['cafeName']}: {str(e)}")
            logger.error(f"Full error: {type(e).__name__}: {str(e)}")
            return cafe_info
    
    async def generate_rich_text(self, prompt: str, context: Dict) -> Dict:
        """Generate rich text content in Contentful format.
        
        Args:
            prompt: The prompt template to use
            context: Dictionary containing context for the generation
        
        Returns:
            Dictionary in Contentful rich text format
        """
        # Check cache first
        cache_key = f"rich_text_{hash(prompt)}_{hash(str(context))}"
        cached_result = cache_manager.load('api_responses', cache_key)
        if cached_result:
            return cached_result
        
        # TODO: Implement actual API call when OpenAI key is available
        # For now, return basic structure
        logger.info(f"OpenAI API not configured yet - would generate rich text for {context.get('section', 'unknown')}")
        return {
            "nodeType": "document",
            "data": {},
            "content": [
                {
                    "nodeType": "paragraph",
                    "content": [
                        {
                            "nodeType": "text",
                            "value": "Placeholder text",
                            "marks": [],
                            "data": {}
                        }
                    ],
                    "data": {}
                }
            ]
        } 