import asyncio
import json
import time
from datetime import date

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
    ContentfulArticlePayload,
    ContentType,
    ContentTypeSys,
    Entry,
    EntrySys,
    Fields,
)
from .utils.logging import setup_logger

logger = setup_logger(__name__)


def _build_article_prompt_from_schema() -> str:
    """Build the article generation prompt dynamically from the Fields schema."""
    # Get the schema from the Fields model
    schema = Fields.schema()

    # Extract field descriptions and requirements
    field_info = []
    for field_name, field in schema["properties"].items():
        if "description" in field:
            field_info.append(f"- {field_name}: {field['description']}")

    return (
        "You are a coffee expert creating a detailed article. Your response MUST be a valid JSON object with the following structure:\n\n"
        "{\n"
        '  "entries": [{\n'
        '    "sys": {\n'
        '      "contentType": {\n'
        '        "sys": {\n'
        '          "type": "Link",\n'
        '          "linkType": "ContentType",\n'
        '          "id": "coffeeArticle"\n'
        "        }\n"
        "      }\n"
        "    },\n"
        '    "fields": {\n'
        '      // All fields below must be wrapped in {"en-US": value}\n'
        '      // Example: "articleTitle": {"en-US": "Article Title"}\n'
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
        "1. Rich text fields (articleContent) must be in this format:\n"
        '{"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "Your text here", "marks": [], "data": {}}]}]}}\n\n'
        "2. Date fields must be in YYYY-MM-DD format\n"
        "3. Boolean fields must be true/false\n"
        "4. Array fields must be lists\n\n"
        "IMPORTANT CONTENT GUIDELINES:\n"
        "1. Article content should be well-structured with proper headings and paragraphs\n"
        "2. Use appropriate formatting for lists and emphasis\n"
        "3. Include relevant keywords naturally in the content\n"
        "4. Maintain a consistent tone throughout the article\n"
        "5. Ensure all content is accurate and informative\n"
    )


class LLMClient:
    def __init__(self):
        """Initialize the LLM client."""
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

        logger.debug("Initialized LLMClient with:")
        logger.debug(f"- Model: {self.model}")
        logger.debug(f"- Temperature: {self.temperature}")
        logger.debug(f"- Max tokens: {self.max_tokens}")
        logger.debug(f"- Base URL: {self.base_url}")

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

    async def generate_article(self, article_data: dict) -> ContentfulArticlePayload:
        """Generate article content using the LLM.

        Args:
            article_data: Dictionary containing article information (title, outline, etc.)

        Returns:
            ContentfulArticlePayload object containing the generated article
        """
        logger.info(f"Generating article: {article_data['title']}")

        # Build the prompt
        article_requirements = _build_article_prompt_from_schema()

        # Prepare messages for the API call
        messages = [
            {
                "role": "system",
                "content": "You are a coffee expert creating detailed, engaging content about coffee. Focus on accuracy and specificity in your articles.",
            },
            {
                "role": "user",
                "content": (
                    f"Create an article with the following information:\n"
                    f"Title: {article_data['title']}\n"
                    f"Outline: {json.dumps(article_data['outline'], indent=2)}\n"
                    f"Target Length: {article_data['targetLength']}\n"
                    f"Keywords: {', '.join(article_data['targetKeywords'])}\n"
                    f"Tone: {article_data['tone']}\n"
                    f"Additional Context: {article_data['additionalContext']}\n\n"
                    f"{article_requirements}\n\n"
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
            # Parse the response as a complete ContentfulArticlePayload
            response_json = json.loads(response)

            # Extract the fields from the first entry
            fields = response_json["entries"][0]["fields"]

            # Set today's date as the publish date
            fields["articlePublishDate"] = {"en-US": date.today().strftime("%Y-%m-%d")}

            # Always set author name to Chris Jordan
            fields["authorName"] = {"en-US": "Chris Jordan"}

            # Create the complete Entry object
            entry = Entry(
                sys=EntrySys(
                    contentType=ContentType(
                        sys=ContentTypeSys(
                            type="Link", linkType="ContentType", id="coffeeArticle"
                        )
                    )
                ),
                fields=Fields(**fields),
            )

            # Create and return the complete payload
            return ContentfulArticlePayload(entries=[entry])

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"Invalid response format from LLM: {e}")
