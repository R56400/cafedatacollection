import time
import logging
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

logger = setup_logger(__name__)
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
    
    async def _make_openai_request(self, messages: List[Dict]) -> Dict:
        """Make a request to the OpenAI API.
        
        Args:
            messages: List of message dictionaries for the conversation
            
        Returns:
            The response from the API
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
            
        self._respect_rate_limit()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error making OpenAI request: {e}")
            raise

    async def get_cafes_for_city(self, city: str, count: int) -> List[Dict]:
        """Get a list of cafes for a given city.
        
        Args:
            city: Name of the city
            count: Number of cafes to retrieve
        
        Returns:
            List of dictionaries containing basic cafe information
        """
        # Check cache first
        cache_key = f"cafes_{city}_{count}"
        cached_result = cache_manager.load('api_responses', cache_key)
        if cached_result:
            return cached_result
            
        # Load and format the prompt
        prompt = self.templates['cafe_search'].format(
            city=city,
            count=count
        )
        
        messages = [
            {"role": "system", "content": "You are a knowledgeable coffee expert."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self._make_openai_request(messages)
            content = response['choices'][0]['message']['content']
            
            # Parse the JSON response
            cafes = json.loads(content)
            if not isinstance(cafes, list):
                cafes = [cafes]  # Handle single cafe response
                
            # Cache the result
            cache_manager.save(
                'api_responses',
                cache_key,
                cafes,
                ttl=CACHE_TTL['api_responses']
            )
            
            return cafes
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI response for {city}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting cafes for {city}: {e}")
            return []
    
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
        
        # TODO: Implement actual API call when OpenAI key is available
        # For now, return input unchanged
        logger.info(f"OpenAI API not configured yet - would enrich details for {cafe_info['cafeName']}")
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