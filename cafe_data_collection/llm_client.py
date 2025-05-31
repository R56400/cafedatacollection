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


def _build_enrichment_prompt_from_schema() -> str:
    """Build the enrichment prompt dynamically from the Fields schema."""
    # Get scoring field descriptions from the schema
    schema = Fields.schema()

    # Extract scoring guidelines from field descriptions
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

    return (
        "Create a detailed review in valid JSON format. The response must be a SINGLE JSON object with this exact structure:\n\n"
        "{\n"
        '  "entries": [{\n'
        '    "sys": {"contentType": {"sys": {"type": "Link", "linkType": "ContentType", "id": "cafeReview"}}},\n'
        '    "fields": {\n'
        '      "cafeName": {"en-US": "NAME"},\n'
        '      "authorName": {"en-US": "Chris Jordan"},\n'
        '      "publishDate": {"en-US": "YYYY-MM-DD"},\n'
        '      "slug": {"en-US": "cafe-name-street"},\n'
        '      "excerpt": {"en-US": "One sentence summary"},\n'
        '      "instagramLink": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "hyperlink", "data": {"uri": "https://instagram.com/cafe"}, "content": [{"nodeType": "text", "value": "Instagram", "marks": [], "data": {}}]}]}]}},\n'
        '      "facebookLink": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "hyperlink", "data": {"uri": "https://facebook.com/cafe"}, "content": [{"nodeType": "text", "value": "Facebook", "marks": [], "data": {}}]}]}]}},\n'
        '      "overallScore": {"en-US": OVERALL_SCORE_NUMBER},\n'
        '      "coffeeScore": {"en-US": COFFEE_SCORE_NUMBER},\n'
        '      "atmosphereScore": {"en-US": ATMOSPHERE_SCORE_NUMBER},\n'
        '      "serviceScore": {"en-US": SERVICE_SCORE_NUMBER},\n'
        '      "vibeScore": {"en-US": VIBE_SCORE_NUMBER},\n'
        '      "vibeDescription": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "3 sentences about vibe", "marks": [], "data": {}}]}]}},\n'
        '      "theStory": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "3-5 sentences about story", "marks": [], "data": {}}]}]}},\n'
        '      "craftExpertise": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "5 sentences about craft", "marks": [], "data": {}}]}]}},\n'
        '      "setsApart": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "3-4 sentences about uniqueness", "marks": [], "data": {}}]}]}},\n'
        '      "cafeAddress": {"en-US": "FULL_ADDRESS"},\n'
        '      "cityReference": {"en-US": {"sys": {"type": "Link", "linkType": "Entry", "id": "CITY_ID"}}}\n'
        "    }\n"
        "  }]\n"
        "}\n\n"
        f"SCORING GUIDELINES (Use actual numbers, not the placeholders above):\n"
        f"{guidelines_text}\n\n"
        "IMPORTANT:\n"
        "1. Response must be VALID JSON\n"
        "2. Replace ALL CAPS placeholders with actual values\n"
        "3. Generate unique, realistic scores for this specific cafe\n"
        "4. Use the full scoring range - don't default to generic scores\n"
        "5. Scores should reflect the cafe's actual quality and reputation"
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
        # Log the input data for debugging
        logger.debug(f"Enriching cafe with data: {json.dumps(cafe_info, indent=2)}")

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

        # Add delay between requests to respect rate limits
        await asyncio.sleep(2)  # 2 second delay between requests

        # Make the API call
        response = await self._make_openai_request(messages)

        if not response:
            logger.error("No response received from OpenAI API")
            raise ValueError("Failed to get response from OpenAI API")

        try:
            # Log the first and last 500 characters of the response
            logger.error(f"Response first 500 chars: {repr(response[:500])}")
            logger.error(f"Response last 500 chars: {repr(response[-500:])}")

            # Try to parse the response
            response_json = json.loads(response)

            # Extract the fields from the first entry
            fields = response_json["entries"][0]["fields"]

            # Set today's date as the publish date
            fields["publishDate"] = {"en-US": date.today().strftime("%Y-%m-%d")}

            # Set the placeId from our geocoding data
            fields["placeId"] = {"en-US": cafe_info["placeId"]}

            # Set the coordinates from our geocoding data
            fields["cafeLatLon"] = {
                "en-US": {"lat": cafe_info["latitude"], "lon": cafe_info["longitude"]}
            }

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
            logger.error(
                f"Failed to parse LLM response for cafe '{cafe_info.get('cafeName', 'unknown')}': {e}"
            )
            logger.error(f"Full response length: {len(response)} characters")
            # Save the problematic response to a file for inspection
            error_file = Path(
                f"error_response_{cafe_info.get('cafeName', 'unknown').replace(' ', '_')}.txt"
            )
            with open(error_file, "w") as f:
                f.write(response)
            logger.error(f"Problematic response saved to: {error_file}")
            raise ValueError(f"Invalid response format from LLM: {e}")
