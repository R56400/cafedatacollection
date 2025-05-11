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
        self.output_dir = Path("articles/outputs")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.llm_client = LLMClient()

    def step1_load_input_data(self) -> dict:
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
            logger.error(f"Attempted to load file at: {self.input_file.absolute()}")
            raise

    async def step2_generate_article(
        self, article_data: dict
    ) -> ContentfulArticlePayload:
        """Generate article content using the LLM.

        Args:
            article_data: Dictionary containing article information

        Returns:
            ContentfulArticlePayload object containing the generated article
        """
        logger.info(f"Generating article: {article_data['title']}")

        # Build the prompt
        prompt = (
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
            '      "articleTitle": {"en-US": "Your Article Title"},\n'
            '      "articleSlug": {"en-US": "your-article-slug"},\n'
            '      "authorName": {"en-US": "Chris Jordan"},\n'
            '      "articleHeroImage": {"en-US": {"sys": {"type": "Link", "linkType": "Asset", "id": "placeholder-image-id"}}},\n'
            '      "articleExcerpt": {"en-US": "A brief summary of your article"},\n'
            '      "articleContent": {"en-US": {"nodeType": "document", "data": {}, "content": [{"nodeType": "paragraph", "data": {}, "content": [{"nodeType": "text", "value": "Your article content here", "marks": [], "data": {}}]}]}},\n'
            '      "articleTags": {"en-US": []},\n'
            '      "articleFeatured": {"en-US": false},\n'
            '      "articleGallery": {"en-US": []},\n'
            '      "videoEmbed": {"en-US": ""}\n'
            "    }\n"
            "  }]\n"
            "}\n\n"
            "Article Information:\n"
            f"Title: {article_data['title']}\n"
            f"Outline: {json.dumps(article_data['outline'], indent=2)}\n"
            f"Target Length: {article_data['targetLength']}\n"
            f"Keywords: {', '.join(article_data['targetKeywords'])}\n"
            f"Tone: {article_data['tone']}\n"
            f"Additional Context: {article_data['additionalContext']}\n\n"
            "IMPORTANT: You MUST include ALL fields shown in the example above, with the following requirements:\n"
            "1. articleTitle: The full title of the article\n"
            "2. articleSlug: URL-friendly version of the title (lowercase, hyphens instead of spaces)\n"
            "3. authorName: Always set to 'Chris Jordan'\n"
            "4. articleHeroImage: Use a placeholder image ID for now\n"
            "5. articleExcerpt: A compelling 1 sentence summary\n"
            "6. articleContent: Rich text content in the specified format\n"
            "7. All other fields should be included as shown in the example\n"
            "\nCONTENT STYLE AND DEPTH REQUIREMENTS:\n"
            "- Do NOT use bold headers, section titles, or explicit headings within the main article content.\n"
            "- Write in a continuous, multi-paragraph narrative style, as you would find in a magazine feature or high-quality blog post. Paragraphs sould vary in legnth..\n"
            "- Ensure smooth transitions between ideas and sections, weaving the outline points together naturally.\n"
            "- Go into significant depth on each topic, providing detailed explanations, examples, and context.\n"
            "- The article should not feel rushed or superficial or too synthetic.\n"
            "- Use a storytelling approach, focusing on flow, engagement, and depth.\n"
            "- Avoid lists, bullet points, or any formatting that breaks the narrative flow.\n"
            "- Maintain a consistent, engaging, and informative tone throughout.\n"
        )

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
            # Parse the response
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

    def step3_save_output(
        self, payload: ContentfulArticlePayload, output_file: str = None
    ):
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
            # Step 1: Load input data
            input_data = self.step1_load_input_data()
            print(
                f"\nStep 1 Complete: Loaded data for {len(input_data['articles'])} articles"
            )

            # Step 2: Generate articles
            for article in input_data["articles"]:
                print(f"\nGenerating article: {article['title']}")
                payload = await self.step2_generate_article(article)
                print(f"Article generation complete: {article['title']}")

                # Step 3: Save output
                output_file = (
                    self.output_dir
                    / f"article_{article['title'].lower().replace(' ', '_')}.json"
                )
                self.step3_save_output(payload, output_file)
                print(f"Saved article to: {output_file}")

            logger.info("Pipeline completed successfully")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
