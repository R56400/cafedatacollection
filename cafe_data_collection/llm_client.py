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
                            "max_tokens": self.max_tokens,
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

    async def _make_structured_openai_request(
        self, messages: list[dict[str, str]], response_format
    ) -> any:
        """Make a structured output request using OpenAI's beta parse endpoint."""
        retries = 0
        while retries < MAX_RETRIES:
            try:
                logger.debug("Preparing structured OpenAI API request")
                logger.debug(
                    f"Request details: model={self.model}, temperature={self.temperature}"
                )

                # Respect rate limits before making request
                self._respect_rate_limit()

                # Use the new structured outputs format
                async with httpx.AsyncClient() as client:
                    # Get the JSON schema from the Pydantic model
                    schema = response_format.model_json_schema()

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
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": schema.get("title", "response"),
                                    "schema": schema,
                                    "strict": True,
                                },
                            },
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

                    if "choices" not in result or not result["choices"]:
                        logger.error("No choices in API response")
                        return None

                    message = result["choices"][0]["message"]

                    # Check for refusal
                    if "refusal" in message and message["refusal"]:
                        logger.error(
                            f"OpenAI refused the request: {message['refusal']}"
                        )
                        raise ValueError(
                            f"OpenAI refused the request: {message['refusal']}"
                        )

                    # Parse the structured response
                    content = message["content"]
                    parsed_data = json.loads(content)
                    validated_response = response_format(**parsed_data)

                    logger.info(
                        "Successfully received structured response from OpenAI API"
                    )
                    return validated_response

            except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                retries += 1
                if retries == MAX_RETRIES:
                    logger.error(
                        f"Max retries ({MAX_RETRIES}) reached. Last error: {str(e)}"
                    )
                    raise
                wait_time = RETRY_DELAY * (2 ** (retries - 1))
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
        """Enrich basic cafe information with detailed content using structured outputs.

        Args:
            cafe_info: Dictionary containing basic cafe information

        Returns:
            ContentfulCafeReviewPayload object containing enriched cafe information
        """

        # Create scoring guidelines from the schema
        schema = Fields.schema()
        scoring_guidelines = []
        score_fields = [
            "overallScore",
            "coffeeScore",
            "atmosphereScore",
            "serviceScore",
            "vibeScore",
        ]

        for field in score_fields:
            if (
                field in schema["properties"]
                and "description" in schema["properties"][field]
            ):
                description = schema["properties"][field]["description"]
                scoring_guidelines.append(f"- {field}: {description}")

        guidelines_text = (
            "\n".join(scoring_guidelines)
            if scoring_guidelines
            else "Use appropriate scoring based on cafe quality."
        )

        # Prepare messages for the API call
        messages = [
            {
                "role": "system",
                "content": f"""You are a coffee expert creating detailed, engaging content about cafes. 
                
SCORING GUIDELINES:
{guidelines_text}

CONTENT GUIDELINES:
- Write naturally and engagingly, as if describing the cafe to friends
- Be specific and detailed in your descriptions
- Focus on what makes each cafe unique
- Use the full scoring range appropriately
- Generate realistic scores based on the cafe's reputation and characteristics""",
            },
            {
                "role": "user",
                "content": f"""Create a comprehensive review for {cafe_info["cafeName"]} located at {cafe_info["cafeAddress"]} in {cafe_info["city"]}.

Brief description: {cafe_info.get("excerpt", "")}

Requirements:
- Use today's date ({date.today().strftime("%Y-%m-%d")}) as the publish date
- Set authorName to "Chris Jordan"
- Only use open cafes, not closed ones
- Generate realistic, varied scores (don't use placeholder scores like 8.2, 8.1, etc.)
- Create engaging, detailed content for all text fields
- Use the city reference ID: {cafe_info["cityReference"]}
- Include the place ID: {cafe_info["placeId"]}
- Use coordinates: lat={cafe_info["latitude"]}, lon={cafe_info["longitude"]}
- Address: {cafe_info["cafeAddress"]}""",
            },
        ]

        # Add delay between requests to respect rate limits
        await asyncio.sleep(2)

        # Make the structured API call
        try:
            fields_response = await self._make_structured_openai_request(
                messages, Fields
            )

            # Create the complete Entry object
            entry = Entry(
                sys=EntrySys(
                    contentType=ContentType(
                        sys=ContentTypeSys(
                            type="Link", linkType="ContentType", id="cafeReview"
                        )
                    )
                ),
                fields=fields_response,
            )

            # Create and return the complete payload
            return ContentfulCafeReviewPayload(entries=[entry])

        except Exception as e:
            logger.error(
                f"Failed to enrich cafe details for '{cafe_info.get('cafeName', 'unknown')}': {e}"
            )
            raise ValueError(f"Failed to enrich cafe details: {e}")
