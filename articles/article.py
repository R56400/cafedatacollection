import json
from datetime import date
from pathlib import Path

from .llm_client import LLMClient
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


class ArticlePipeline:
    """A pipeline for article generation, broken into discrete steps."""

    def __init__(self, input_file: str):
        """Initialize the pipeline.

        Args:
            input_file: Path to JSON file with article data
        """
        self.input_file = Path(input_file)
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)

        # Initialize components
        self.llm_client = LLMClient()

    def _load_input_data(self) -> dict:
        """Load and validate input data.

        Returns:
            Dictionary containing the article data
        """
        logger.info(f"Loading input data from {self.input_file}")

        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "articles" not in data:
                raise ValueError("Input file must contain 'articles' key")

            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse input JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading input file: {e}")
            raise

    def _build_article_prompt(self, article_data: dict) -> str:
        """Build the prompt for article generation.

        Args:
            article_data: Dictionary containing article information

        Returns:
            Formatted prompt string
        """
        # Get the schema from the Fields model
        schema = Fields.schema()

        # Extract field descriptions and requirements
        field_info = []
        for field_name, field in schema["properties"].items():
            if "description" in field:
                field_info.append(f"- {field_name}: {field['description']}")

        return (
            "You are a coffee expert creating an article. Your response MUST be a valid JSON object with the following structure:\n\n"
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
            "    }\n"
            "  }]\n"
            "}\n\n"
            "IMPORTANT: The response MUST:\n"
            "1. Include the complete 'entries' wrapper and 'sys' object exactly as shown above\n"
            "2. Wrap ALL field values in {'en-US': value}\n"
            "3. Follow the specific format requirements for each field type\n\n"
            "Article Information:\n"
            f"Title: {article_data['title']}\n"
            f"Outline: {json.dumps(article_data['outline'], indent=2)}\n"
            f"Target Length: {article_data['targetLength']}\n"
            f"Keywords: {', '.join(article_data['targetKeywords'])}\n"
            f"Tone: {article_data['tone']}\n"
            f"Additional Context: {article_data['additionalContext']}\n\n"
            "Each field must follow these requirements:\n\n"
            + "\n".join(field_info)
            + "\n\nIMPORTANT FIELD FORMATS:\n\n"
            "1. Rich text fields (articleContent) must be in this format:\n"
            '{"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "Your text here", "marks": [], "data": {}}]}]}}\n\n'
            "2. Date fields must be in YYYY-MM-DD format\n"
            "3. Boolean fields must be true/false\n"
            "4. Array fields must be lists\n\n"
        )

    async def generate_article(self, article_data: dict) -> ContentfulArticlePayload:
        """Generate article content using the LLM.

        Args:
            article_data: Dictionary containing article information

        Returns:
            ContentfulArticlePayload object containing the generated article
        """
        logger.info(f"Generating article: {article_data['title']}")

        # Build the prompt
        prompt = self._build_article_prompt(article_data)

        # Prepare messages for the API call
        messages = [
            {
                "role": "system",
                "content": "You are a coffee expert creating detailed, engaging content about coffee. Focus on accuracy and specificity in your articles.",
            },
            {"role": "user", "content": prompt},
        ]

        # Make the API call
        response = await self.llm_client._make_openai_request(messages)

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

    def save_output(self, payload: ContentfulArticlePayload, output_file: str = None):
        """Save the generated article to a file.

        Args:
            payload: ContentfulArticlePayload object
            output_file: Optional specific output file path
        """
        if output_file is None:
            output_file = self.output_dir / "generated_articles.json"
        else:
            output_file = Path(output_file)

        logger.info(f"Saving output to {output_file}")

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload.model_dump(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving output file: {e}")
            raise

    async def run_pipeline(self):
        """Run the complete article generation pipeline."""
        try:
            # Load input data
            input_data = self._load_input_data()

            # Process each article
            for article in input_data["articles"]:
                # Generate article content
                payload = await self.generate_article(article)

                # Save output
                self.save_output(payload)

            logger.info("Pipeline completed successfully")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
