import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import List

import httpx

from .config import (
    MAX_RETRIES,
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    RATE_LIMITS,
    RETRY_DELAY,
)
from .schema import (
    ContentfulCafeReviewPayload,
    ContentType,
    ContentTypeSys,
    Entry,
    EntrySys,
    Fields,
)
from .utils.logging import setup_logger

logger = setup_logger(__name__)


def _clean_llm_response(response: str) -> str:
    """Clean the LLM response to extract valid JSON."""
    cleaned = response.strip()

    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    # Try to find JSON content if there's extra text
    # Look for the first { and last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    # Handle Unicode and special characters that might break JSON parsing
    # Replace common problematic characters
    cleaned = cleaned.replace("'", '"')  # Replace single quotes with double quotes
    cleaned = cleaned.replace('"', '"')  # Replace smart quotes with regular quotes
    cleaned = cleaned.replace('"', '"')  # Replace smart quotes with regular quotes
    cleaned = cleaned.replace(
        """, "'")  # Replace smart apostrophes
    cleaned = cleaned.replace(""",
        "'",
    )  # Replace smart apostrophes
    cleaned = cleaned.replace("–", "-")  # Replace en dash with regular dash
    cleaned = cleaned.replace("—", "-")  # Replace em dash with regular dash
    cleaned = cleaned.replace("…", "...")  # Replace ellipsis with three dots

    # Remove any null bytes or other control characters
    cleaned = "".join(char for char in cleaned if ord(char) >= 32 or char in "\n\r\t")

    # Normalize Unicode characters
    import unicodedata

    cleaned = unicodedata.normalize("NFKC", cleaned)

    return cleaned


def _build_enrichment_prompt_from_schema() -> str:
    """Build the enrichment prompt dynamically from the Fields schema."""
    # Get the schema from the Fields model
    schema = Fields.schema()

    # Extract field descriptions and requirements
    field_info = []
    for field_name, field in schema["properties"].items():
        if "description" in field:
            field_info.append(f"- {field_name}: {field['description']}")

    return (
        "You are a coffee expert creating a detailed review. Your response MUST be a valid JSON object with the following structure:\n\n"
        "{\n"
        '  "entries": [{\n'
        '    "sys": {\n'
        '      "contentType": {\n'
        '        "sys": {\n'
        '          "type": "Link",\n'
        '          "linkType": "ContentType",\n'
        '          "id": "cafeReview"\n'
        "        }\n"
        "      }\n"
        "    },\n"
        '    "fields": {\n'
        '      // All fields below must be wrapped in {"en-US": value}\n'
        '      // Example: "cafeName": {"en-US": "Coffee Shop Name"}\n'
        "    }\n"
        "  }]\n"
        "}\n\n"
        "IMPORTANT: The response MUST:\n"
        "1. Include the complete 'entries' wrapper and 'sys' object exactly as shown above\n"
        "2. Wrap ALL field values in {'en-US': value}\n"
        "3. Follow the specific format requirements for each field type\n\n"
        "Each field must follow these requirements:\n\n"
        + "\n".join(field_info)
        + "\n\nIMPORTANT FIELD FORMATS:\n\n"
        "1. Social media links (instagramLink and facebookLink) must be in this format:\n"
        '{"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "hyperlink", "data": {"uri": "ACTUAL_URL"}, "content": [{"nodeType": "text", "value": "PLATFORM_NAME", "marks": [], "data": {}}]}]}]}}\n\n'
        "2. City reference must be in this format:\n"
        '{"en-US": {"sys": {"type": "Link", "linkType": "Entry", "id": "CITY_REFERENCE_ID"}}}\n\n'
        "3. Rich text fields (like vibeDescription, theStory, etc.) must be in this format:\n"
        '{"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "Your text here", "marks": [], "data": {}}]}]}}\n\n'
        "4. Numeric scores must be wrapped in en-US:\n"
        '{"en-US": 8.5}\n\n'
        "IMPORTANT SCORE FORMATS:\n"
        "- vibeScore must be an integer between 1-10 (no decimals). Example: {'en-US': 8}\n"
        "- All other scores (overallScore, coffeeScore, atmosphereScore, etc.) should be floats with one decimal place. Example: {'en-US': 8.5}\n\n"
        "5. Coordinates must be wrapped in en-US:\n"
        '{"en-US": {"lat": 35.6813, "lon": -105.9787}}\n\n'
    )


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

        logger.debug(f"LLMClient initialized with API key length: {len(self.api_key)}")
        logger.debug(f"API key starts with 'sk-': {self.api_key.startswith('sk-')}")
        logger.debug(f"API key preview: {self.api_key[:10]}...{self.api_key[-4:]}")

        # Load only the cafe search template
        self.cafe_search_template = self._load_template("cafe_search.txt")

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
        retries = 0
        while retries < MAX_RETRIES:
            try:
                logger.debug("Preparing OpenAI API request")
                logger.debug(
                    f"Request details: model={self.model}, temperature={self.temperature}, max_tokens={self.max_tokens}"
                )
                logger.debug(f"Messages to send: {json.dumps(messages, indent=2)}")

                # Respect rate limits before making request
                self._respect_rate_limit()

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
                            "max_completion_tokens": self.max_tokens,
                        },
                        timeout=90.0,
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

            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                retries += 1
                if retries == MAX_RETRIES:
                    logger.error(
                        f"Max retries ({MAX_RETRIES}) reached. Last error: {str(e)}"
                    )
                    raise
                wait_time = RETRY_DELAY * (2 ** (retries - 1))  # Exponential backoff
                logger.warning(
                    f"Request timed out. Retrying in {wait_time} seconds... (Attempt {retries + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Unexpected error occurred: {str(e)}")
                logger.debug(f"Error type: {type(e).__name__}")
                raise

    async def get_cafes_for_city(self, city: str, num_cafes: int = 5) -> List[dict]:
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
                # Basic validation of required fields
                validated_cafes = []
                for cafe in cafes:
                    if all(
                        key in cafe
                        for key in [
                            "cafeName",
                            "cafeAddress",
                            "city",
                            "excerpt",
                        ]
                    ):
                        validated_cafes.append(cafe)
                    else:
                        logger.warning(f"Cafe missing required fields: {cafe}")
                logger.info(
                    f"Successfully parsed and validated {len(validated_cafes)} cafes from response"
                )
                return validated_cafes
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {response}")
                return []

        except Exception as e:
            logger.error(f"Error getting cafes for {city}: {str(e)}")
            raise

    async def enrich_cafe_details(self, cafe_info: dict) -> ContentfulCafeReviewPayload:
        """Enrich basic cafe information with detailed content.

        Args:
            cafe_info: Dictionary containing basic cafe information

        Returns:
            ContentfulCafeReviewPayload object containing enriched cafe information matching the Contentful structure
        """
        # Build the prompt from the schema
        enrichment_requirements = _build_enrichment_prompt_from_schema()

        # Prepare messages for the API call
        messages = [
            {
                "role": "system",
                "content": "You are a coffee expert creating detailed, engaging content about cafes. Focus on accuracy and specificity in your reviews.",
            },
            {
                "role": "user",
                "content": (
                    f"Create a detailed review for {cafe_info['cafeName']} in {cafe_info['city']}.\n"
                    f"Brief description: {cafe_info.get('excerpt', '')}\n"
                    f"Address: {cafe_info['cafeAddress']}\n"
                    f"City Reference for context: {cafe_info['cityReference']}\n\n"
                    f"{enrichment_requirements}\n\n"
                    "Provide the response as a single JSON object. Do not include any markdown formatting or additional text."
                ),
            },
        ]

        # Make the API call
        response = await self._make_openai_request(messages)

        if not response:
            logger.error("No response received from OpenAI API")
            raise ValueError("Failed to get response from OpenAI API")

        try:
            # Clean the response before parsing
            cleaned_response = _clean_llm_response(response)
            logger.debug(f"Original response length: {len(response)}")
            logger.debug(f"Cleaned response length: {len(cleaned_response)}")

            # Log a preview of the cleaned response for debugging
            preview_length = min(1000, len(cleaned_response))
            logger.debug(
                f"Cleaned response preview: {cleaned_response[:preview_length]}..."
            )

            # Parse the response as a complete ContentfulCafeReviewPayload
            try:
                response_json = json.loads(cleaned_response)
            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parsing error: {json_error}")
                logger.error(
                    f"Error position: line {json_error.lineno}, column {json_error.colno}, char {json_error.pos}"
                )

                # Show the problematic area around the error
                lines = cleaned_response.split("\n")
                if json_error.lineno <= len(lines):
                    problematic_line = lines[json_error.lineno - 1]
                    logger.error(
                        f"Problematic line {json_error.lineno}: {problematic_line}"
                    )

                    # Show the character at the error position
                    if json_error.pos < len(cleaned_response):
                        char_at_error = cleaned_response[json_error.pos]
                        logger.error(
                            f"Character at error position: '{char_at_error}' (ord: {ord(char_at_error)})"
                        )

                    # Show context lines
                    if json_error.lineno > 1:
                        logger.error(
                            f"Previous line {json_error.lineno - 1}: {lines[json_error.lineno - 2]}"
                        )
                    if json_error.lineno < len(lines):
                        logger.error(
                            f"Next line {json_error.lineno + 1}: {lines[json_error.lineno]}"
                        )

                raise json_error

            # Extract the fields from the first entry
            fields = response_json["entries"][0]["fields"]

            # Set today's date as the publish date
            fields["publishDate"] = {"en-US": date.today().strftime("%Y-%m-%d")}

            # Ensure proper structure for social media links and city reference
            if "instagramLink" in fields and isinstance(
                fields["instagramLink"].get("en-US"), str
            ):
                url = fields["instagramLink"]["en-US"]
                fields["instagramLink"]["en-US"] = {
                    "nodeType": "document",
                    "data": {},
                    "content": [
                        {
                            "nodeType": "paragraph",
                            "data": {},
                            "content": [
                                {
                                    "nodeType": "hyperlink",
                                    "data": {"uri": url},
                                    "content": [
                                        {
                                            "nodeType": "text",
                                            "value": "Instagram",
                                            "marks": [],
                                            "data": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }

            if "facebookLink" in fields and isinstance(
                fields["facebookLink"].get("en-US"), str
            ):
                url = fields["facebookLink"]["en-US"]
                fields["facebookLink"]["en-US"] = {
                    "nodeType": "document",
                    "data": {},
                    "content": [
                        {
                            "nodeType": "paragraph",
                            "data": {},
                            "content": [
                                {
                                    "nodeType": "hyperlink",
                                    "data": {"uri": url},
                                    "content": [
                                        {
                                            "nodeType": "text",
                                            "value": "Facebook",
                                            "marks": [],
                                            "data": {},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }

            if "cityReference" in fields and isinstance(
                fields["cityReference"].get("en-US"), str
            ):
                city_reference_id = cafe_info["cityReference"]
                fields["cityReference"]["en-US"] = {
                    "sys": {
                        "type": "Link",
                        "linkType": "Entry",
                        "id": city_reference_id,
                    }
                }

            # Set the placeId from our geocoding data
            fields["placeId"] = {"en-US": cafe_info["placeId"]}

            # Set the coordinates from our geocoding data
            fields["cafeLatLon"] = {
                "en-US": {"lat": cafe_info["latitude"], "lon": cafe_info["longitude"]}
            }

            # Validate fields
            validated_fields = Fields(**fields)

            # Create the complete Entry object
            entry = Entry(
                sys=EntrySys(
                    contentType=ContentType(
                        sys=ContentTypeSys(
                            type="Link", linkType="ContentType", id="cafeReview"
                        )
                    )
                ),
                fields=validated_fields,
            )

            # Create and return the complete payload
            return ContentfulCafeReviewPayload(entries=[entry])

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Invalid response format from LLM: {e}")
