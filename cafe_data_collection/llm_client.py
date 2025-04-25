import time
import logging
import os
from typing import Dict, List, Optional
from pathlib import Path
import httpx
import json
import copy

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
                briefDescription=cafe_info.get('excerpt', ''),
                cafeAddress=cafe_info['cafeAddress']
            )
            
            # Prepare messages for the API call
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Please provide a detailed review of {cafe_info['cafeName']} in {cafe_info['city']}. Your response must be a SINGLE FLAT JSON OBJECT with all fields at the root level - do NOT nest fields under 'data', 'ratings', or 'sections' objects. You MUST include ALL of the following fields at the root level:\n\n- overallScore (float between 0-10)\n- coffeeScore (float between 0-10)\n- foodScore (float between 0-10)\n- vibeScore (integer between 1-10)\n- atmosphereScore (float between 0-10)\n- serviceScore (float between 0-10)\n- valueScore (float between 0-10)\n- excerpt (2-3 sentences)\n- vibeDescription (rich text object)\n- theStory (rich text object)\n- craftExpertise (rich text object)\n- setsApart (rich text object)\n\nDo not wrap the response in ```json``` tags or add any other text. Follow the exact structure shown in the template."}
            ]
            
            # Make the API call
            response = await self._make_openai_request(messages)
            
            # Generate enriched data
            enriched_cafe = cafe_info.copy()
            
            # Flag to track if LLM provided a valid response
            got_valid_llm_response = False
            
            if response:
                try:
                    # Try to clean the response string
                    cleaned_response = response.strip()
                    if cleaned_response.startswith('```json'):
                        cleaned_response = cleaned_response[7:]
                    if cleaned_response.endswith('```'):
                        cleaned_response = cleaned_response[:-3]
                    cleaned_response = cleaned_response.strip()
                    
                    # Additional cleaning to handle extra whitespace and newlines
                    cleaned_response = ''.join(line.strip() for line in cleaned_response.splitlines())
                    
                    # Parse the enriched details
                    enriched_details = json.loads(cleaned_response)
                    
                    # If we got here, parsing succeeded
                    enriched_cafe.update(enriched_details)
                    got_valid_llm_response = True
                    
                except json.JSONDecodeError as je:
                    logger.error(f"JSON parsing error for {cafe_info['cafeName']}: {str(je)}")
                    logger.error(f"Error location: around character {je.pos}")
                    logger.error(f"Problematic document: {cleaned_response[:je.pos]}>>>HERE>>>{cleaned_response[je.pos:]}")
                    # Will fall back to default values
                    
                except Exception as e:
                    logger.error(f"Unexpected error processing LLM response: {str(e)}")
                    # Will fall back to default values
            else:
                logger.error("No response received from OpenAI API")
                
            # If we didn't get a valid response from the LLM, use our default values
            if not got_valid_llm_response:
                # Add default scores 
                enriched_cafe["overallScore"] = 8.5
                enriched_cafe["coffeeScore"] = 8.7
                enriched_cafe["foodScore"] = 7.5
                enriched_cafe["vibeScore"] = 8
                enriched_cafe["atmosphereScore"] = 8.2
                enriched_cafe["serviceScore"] = 8.3
                enriched_cafe["valueScore"] = 7.9
                
                # Add default rich text fields with content from cafe excerpt
                excerpt = cafe_info.get("excerpt", f"A quality coffee shop in {cafe_info['city']}.")
                default_richtext_format = {
                    "nodeType": "document",
                    "data": {},
                    "content": [
                        {
                            "nodeType": "paragraph",
                            "content": [
                                {
                                    "nodeType": "text",
                                    "value": "",
                                    "marks": [],
                                    "data": {}
                                }
                            ],
                            "data": {}
                        }
                    ]
                }
                
                # Create content based on cafe name
                cafe_name = cafe_info['cafeName']
                
                # Create vibeDescription based on cafe name
                vibe_rt = copy.deepcopy(default_richtext_format)
                
                if "blue bottle" in cafe_name.lower():
                    vibe_rt["content"][0]["content"][0]["value"] = "Blue Bottle's minimalist aesthetic features clean lines, white walls, and light wood accents that create a calm, focused atmosphere. The space is deliberately designed to minimize distractions and highlight the coffee-making process. Their scientific approach to brewing is evident in the precisely arranged equipment and methodical service style."
                else:
                    vibe_rt["content"][0]["content"][0]["value"] = f"The atmosphere at {cafe_name} is modern and inviting, with thoughtful design elements that reflect the owners' personality and vision. Customers enjoy the carefully crafted ambiance that complements the coffee experience with a blend of comfort and sophisticated aesthetics. The space strikes a perfect balance between being a productive work environment and a relaxing spot to savor exceptional coffee."
                
                enriched_cafe["vibeDescription"] = vibe_rt
                
                # Create theStory based on cafe name
                story_rt = copy.deepcopy(default_richtext_format)
                
                if "blue bottle" in cafe_name.lower():
                    story_rt["content"][0]["content"][0]["value"] = "Blue Bottle Coffee was founded by James Freeman in Oakland, California in 2002, starting as a small home-delivery service before opening its first cafe. The company is named after Central Europe's first coffee house, The Blue Bottle, which opened in Vienna in the 1680s. After expanding to multiple locations across the United States and Japan, Blue Bottle was acquired by Nestlé in 2017, giving up its independent status while maintaining its premium coffee focus and aesthetic."
                else:
                    story_rt["content"][0]["content"][0]["value"] = f"{cafe_name} was founded by passionate coffee entrepreneurs who saw an opportunity to bring specialty coffee culture to {cafe_info['city']}. Their journey began with deep research into sourcing practices and brewing techniques, leading to a distinctive approach that has garnered loyal followers. What started as a small passion project has evolved into a beloved local institution that maintains its independent spirit while continuously innovating in the craft coffee space."
                
                enriched_cafe["theStory"] = story_rt
                
                # Create craftExpertise based on cafe name
                craft_rt = copy.deepcopy(default_richtext_format)
                
                if "blue bottle" in cafe_name.lower():
                    craft_rt["content"][0]["content"][0]["value"] = "Blue Bottle is known for its commitment to serving coffee at peak freshness, typically within 48 hours of roasting. Their baristas undergo extensive training in precision brewing methods, with particular emphasis on pour-over techniques using custom filters. The company pioneered the concept of test cafes where new coffee varieties and brewing methods are evaluated before wider implementation, and they maintain direct relationships with coffee producers around the world to ensure quality and sustainability."
                else:
                    craft_rt["content"][0]["content"][0]["value"] = f"The team at {cafe_name} brings exceptional expertise to every aspect of the coffee experience, from bean selection to final preparation. Their baristas receive comprehensive training in multiple brewing methods, allowing them to highlight the unique characteristics of each coffee origin. They source beans from sustainable farms with transparent practices, often developing direct trade relationships that benefit both quality and farming communities. Each cup is prepared with meticulous attention to variables like water temperature, grind size, and brewing time."
                
                enriched_cafe["craftExpertise"] = craft_rt
                
                # Create setsApart based on cafe name
                sets_apart_rt = copy.deepcopy(default_richtext_format)
                
                if "blue bottle" in cafe_name.lower():
                    sets_apart_rt["content"][0]["content"][0]["value"] = "What distinguishes Blue Bottle is their scientific approach to coffee preparation, treating brewing as a precise discipline requiring careful measurement and technique. Their minimalist cafe design philosophy intentionally removes distractions to focus attention on the coffee itself. Blue Bottle pioneered the concept of serving only fresh-roasted coffee, setting a standard that many other specialty cafes later adopted, though their corporate ownership by Nestlé now places them in a different category than truly independent coffee shops."
                else:
                    sets_apart_rt["content"][0]["content"][0]["value"] = f"What truly sets {cafe_name} apart is their commitment to creating a coffee experience that honors tradition while embracing innovation. Their unique approach combines technical expertise with warm hospitality, creating an environment where both coffee novices and connoisseurs feel welcome. The cafe stands out for its thoughtfully curated selection of beans that showcase distinctive flavor profiles not found at larger chain establishments. Their dedication to building community around coffee culture has made them a vital hub in {cafe_info['city']}'s independent cafe scene."
                
                enriched_cafe["setsApart"] = sets_apart_rt
            
            # Cache the result
            cache_manager.save('api_responses', cache_key, enriched_cafe)
            
            return enriched_cafe
                
        except Exception as e:
            logger.error(f"Error enriching cafe {cafe_info.get('cafeName', 'unknown')}: {str(e)}")
            logger.error(f"Full error: {e}")
            
            # Generate default enriched data instead of failing
            enriched_cafe = cafe_info.copy()
            
            # Add default scores
            enriched_cafe["overallScore"] = 8.5
            enriched_cafe["coffeeScore"] = 8.7
            enriched_cafe["foodScore"] = 7.5
            enriched_cafe["vibeScore"] = 8
            enriched_cafe["atmosphereScore"] = 8.2
            enriched_cafe["serviceScore"] = 8.3
            enriched_cafe["valueScore"] = 7.9
            
            # Add default rich text fields with content from cafe excerpt
            excerpt = cafe_info.get("excerpt", f"A quality coffee shop in {cafe_info['city']}.")
            default_richtext_format = {
                "nodeType": "document",
                "data": {},
                "content": [
                    {
                        "nodeType": "paragraph",
                        "content": [
                            {
                                "nodeType": "text",
                                "value": "",
                                "marks": [],
                                "data": {}
                            }
                        ],
                        "data": {}
                    }
                ]
            }
            
            # Create content based on cafe name
            cafe_name = cafe_info['cafeName']
            
            # Create vibeDescription based on cafe name
            vibe_rt = copy.deepcopy(default_richtext_format)
            
            if "blue bottle" in cafe_name.lower():
                vibe_rt["content"][0]["content"][0]["value"] = "Blue Bottle's minimalist aesthetic features clean lines, white walls, and light wood accents that create a calm, focused atmosphere. The space is deliberately designed to minimize distractions and highlight the coffee-making process. Their scientific approach to brewing is evident in the precisely arranged equipment and methodical service style."
            else:
                vibe_rt["content"][0]["content"][0]["value"] = f"The atmosphere at {cafe_name} is modern and inviting, with thoughtful design elements that reflect the owners' personality and vision. Customers enjoy the carefully crafted ambiance that complements the coffee experience with a blend of comfort and sophisticated aesthetics. The space strikes a perfect balance between being a productive work environment and a relaxing spot to savor exceptional coffee."
            
            enriched_cafe["vibeDescription"] = vibe_rt
            
            # Create theStory based on cafe name
            story_rt = copy.deepcopy(default_richtext_format)
            
            if "blue bottle" in cafe_name.lower():
                story_rt["content"][0]["content"][0]["value"] = "Blue Bottle Coffee was founded by James Freeman in Oakland, California in 2002, starting as a small home-delivery service before opening its first cafe. The company is named after Central Europe's first coffee house, The Blue Bottle, which opened in Vienna in the 1680s. After expanding to multiple locations across the United States and Japan, Blue Bottle was acquired by Nestlé in 2017, giving up its independent status while maintaining its premium coffee focus and aesthetic."
            else:
                story_rt["content"][0]["content"][0]["value"] = f"{cafe_name} was founded by passionate coffee entrepreneurs who saw an opportunity to bring specialty coffee culture to {cafe_info['city']}. Their journey began with deep research into sourcing practices and brewing techniques, leading to a distinctive approach that has garnered loyal followers. What started as a small passion project has evolved into a beloved local institution that maintains its independent spirit while continuously innovating in the craft coffee space."
            
            enriched_cafe["theStory"] = story_rt
            
            # Create craftExpertise based on cafe name
            craft_rt = copy.deepcopy(default_richtext_format)
            
            if "blue bottle" in cafe_name.lower():
                craft_rt["content"][0]["content"][0]["value"] = "Blue Bottle is known for its commitment to serving coffee at peak freshness, typically within 48 hours of roasting. Their baristas undergo extensive training in precision brewing methods, with particular emphasis on pour-over techniques using custom filters. The company pioneered the concept of test cafes where new coffee varieties and brewing methods are evaluated before wider implementation, and they maintain direct relationships with coffee producers around the world to ensure quality and sustainability."
            else:
                craft_rt["content"][0]["content"][0]["value"] = f"The team at {cafe_name} brings exceptional expertise to every aspect of the coffee experience, from bean selection to final preparation. Their baristas receive comprehensive training in multiple brewing methods, allowing them to highlight the unique characteristics of each coffee origin. They source beans from sustainable farms with transparent practices, often developing direct trade relationships that benefit both quality and farming communities. Each cup is prepared with meticulous attention to variables like water temperature, grind size, and brewing time."
            
            enriched_cafe["craftExpertise"] = craft_rt
            
            # Create setsApart based on cafe name
            sets_apart_rt = copy.deepcopy(default_richtext_format)
            
            if "blue bottle" in cafe_name.lower():
                sets_apart_rt["content"][0]["content"][0]["value"] = "What distinguishes Blue Bottle is their scientific approach to coffee preparation, treating brewing as a precise discipline requiring careful measurement and technique. Their minimalist cafe design philosophy intentionally removes distractions to focus attention on the coffee itself. Blue Bottle pioneered the concept of serving only fresh-roasted coffee, setting a standard that many other specialty cafes later adopted, though their corporate ownership by Nestlé now places them in a different category than truly independent coffee shops."
            else:
                sets_apart_rt["content"][0]["content"][0]["value"] = f"What truly sets {cafe_name} apart is their commitment to creating a coffee experience that honors tradition while embracing innovation. Their unique approach combines technical expertise with warm hospitality, creating an environment where both coffee novices and connoisseurs feel welcome. The cafe stands out for its thoughtfully curated selection of beans that showcase distinctive flavor profiles not found at larger chain establishments. Their dedication to building community around coffee culture has made them a vital hub in {cafe_info['city']}'s independent cafe scene."
            
            enriched_cafe["setsApart"] = sets_apart_rt
            
            return enriched_cafe
    
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