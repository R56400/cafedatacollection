import json
import time
from pathlib import Path

import httpx

from .config import (
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    RATE_LIMITS,
)
from .utils.logging import setup_logger

logger = setup_logger(__name__)


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

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY in your .env file."
            )

        # Load templates
        self.cafe_search_template = self._load_template("cafe_search.txt")
        self.cafe_details_template = self._load_template("cafe_details.txt")

        logger.debug("Initialized LLMClient with:")
        logger.debug(f"- Model: {self.model}")
        logger.debug(f"- Temperature: {self.temperature}")
        logger.debug(f"- Max tokens: {self.max_tokens}")
        logger.debug(f"- Base URL: {self.base_url}")

    def _load_template(self, template_name: str) -> str:
        try:
            path = Path(__file__).parent / "templates" / template_name
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning(f"Template not found: {template_name}")
            return None

    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed the rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        # Convert rate limit to seconds
        min_interval = 60.0 / RATE_LIMITS["openai"]

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self.last_request_time = time.time()

    async def _make_openai_request(self, messages: list[dict[str, str]]) -> str | None:
        try:
            logger.debug("Preparing OpenAI API request")
            logger.debug(
                f"Request details: model={self.model}, temperature={self.temperature}, max_tokens={self.max_tokens}"
            )
            logger.debug(f"Messages to send: {json.dumps(messages, indent=2)}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                    },
                    timeout=30.0,
                )

                logger.debug(f"Response status code: {response.status_code}")

                if response.status_code == 401:
                    logger.error("OpenAI API key is invalid")
                    raise ValueError(
                        "Invalid OpenAI API key. Please check your OPENAI_API_KEY in .env"
                    )

                response.raise_for_status()
                result = response.json()
                logger.debug(f"Raw API response: {json.dumps(result, indent=2)}")

                if "choices" not in result or not result["choices"]:
                    logger.error("No choices in API response")
                    logger.debug(f"Full response: {json.dumps(result, indent=2)}")
                    return None

                logger.info("Successfully received response from OpenAI API")
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            logger.debug(f"Error type: {type(e).__name__}")
            raise

    async def get_cafes_for_city(self, city: str, num_cafes: int = 5) -> list[dict]:
        logger.info(f"Getting {num_cafes} cafes for city: {city}")

        try:
            messages = [
                {"role": "system", "content": self.cafe_search_template},
                {"role": "user", "content": f"Find {num_cafes} cafes in {city}"},
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

    async def enrich_cafe_details(self, cafe_info: dict) -> dict:
        """Enrich basic cafe information with detailed content.

        Args:
            cafe_info: Dictionary containing basic cafe information

        Returns:
            Dictionary containing enriched cafe information
        """
        system_content = self.cafe_details_template.format(
            cafeName=cafe_info["cafeName"],
            city=cafe_info["city"],
            briefDescription=cafe_info.get("excerpt", ""),
            cafeAddress=cafe_info["cafeAddress"],
        )

        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"Please provide a detailed review of {cafe_info['cafeName']} in {cafe_info['city']}. Your response must be a SINGLE FLAT JSON OBJECT with all fields at the root level - do NOT nest fields under 'data', 'ratings', or 'sections' objects. You MUST include ALL of the following fields at the root level:\n\n- overallScore (float between 0-10)\n- coffeeScore (float between 0-10)\n- foodScore (float between 0-10)\n- vibeScore (integer between 1-10)\n- atmosphereScore (float between 0-10)\n- serviceScore (float between 0-10)\n- valueScore (float between 0-10)\n- excerpt (2-3 sentences)\n- vibeDescription (rich text object)\n- theStory (rich text object)\n- craftExpertise (rich text object)\n- setsApart (rich text object)\n\nDo not wrap the response in ```json``` tags or add any other text. Follow the exact structure shown in the template.",
            },
        ]

        # Make the API call
        response = await self._make_openai_request(messages)

        # Generate enriched data
        enriched_cafe = cafe_info.copy()

        if response:
            try:
                # Try to clean the response string
                cleaned_response = response.strip()
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                cleaned_response = cleaned_response.strip()

                # Additional cleaning to handle extra whitespace and newlines
                cleaned_response = "".join(
                    line.strip() for line in cleaned_response.splitlines()
                )

                # Parse the enriched details
                enriched_details = json.loads(cleaned_response)

                # If we got here, parsing succeeded
                enriched_cafe.update(enriched_details)

            except json.JSONDecodeError as je:
                logger.error(
                    f"JSON parsing error for {cafe_info['cafeName']}: {str(je)}"
                )
                logger.error(f"Error location: around character {je.pos}")
                logger.error(
                    f"Problematic document: {cleaned_response[: je.pos]}>>>HERE>>>{cleaned_response[je.pos :]}"
                )
                # Will fall back to default values

            except Exception as e:
                logger.error(f"Unexpected error processing LLM response: {str(e)}")
                # Will fall back to default values
        else:
            logger.error("No response received from OpenAI API")

        return enriched_cafe
