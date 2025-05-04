import json
import logging
from pathlib import Path

from .config import LOG_LEVEL, OUTPUT_DIR
from .data_collection import DataCollector
from .geocoding import GeocodingClient
from .llm_client import LLMClient
from .places import PlacesClient
from .utils.logging import setup_logger

logger = setup_logger(__name__, level=getattr(logging, LOG_LEVEL))


class CafePipeline:
    """A pipeline for cafe data collection, broken into discrete steps."""

    def __init__(self, input_csv: str, city_mapping_json: str):
        """Initialize the pipeline.

        Args:
            input_csv: Path to CSV file with city data
            city_mapping_json: Path to JSON file with city ID mappings
        """
        self.input_csv = Path(input_csv)
        self.city_mapping_json = Path(city_mapping_json)
        self.output_dir = Path(OUTPUT_DIR)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Ensure pipeline outputs directory exists
        self.pipeline_dir = self.output_dir / "pipeline"
        self.pipeline_dir.mkdir(exist_ok=True)

        # Initialize components
        self.collector = DataCollector(input_csv, city_mapping_json)
        self.llm_client = LLMClient()
        self.geocoding_client = GeocodingClient()
        self.places_client = PlacesClient()

    def step1_load_input_data(self) -> dict:
        """Step 1: Load input data and create collection queue.

        Returns:
            Dictionary containing the city collection queue
        """
        logger.info("Step 1: Loading input data...")

        # Load city data from CSV and mappings
        self.collector.load_input_data()
        collection_queue = self.collector.get_collection_queue()

        # Save output for review
        output_file = self.pipeline_dir / "step1_city_queue.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(collection_queue, f, indent=2)

        logger.info(f"Step 1 complete. City queue saved to {output_file}")
        return {"collection_queue": collection_queue}

    async def step2_get_cafes_for_city(
        self, city: str, cafes_needed: int, city_reference: str
    ) -> dict:
        """Step 2: Get a list of cafes for a specific city.

        Args:
            city: Name of the city
            cafes_needed: Number of cafes to retrieve
            city_reference: City ID from mapping file

        Returns:
            Dictionary containing the list of cafes
        """
        logger.info(f"Step 2: Getting cafes for {city} (need {cafes_needed})...")

        # Get cafes directly from LLM
        cafes = await self.llm_client.get_cafes_for_city(city, cafes_needed)

        if not cafes:
            logger.error(f"No cafes found for {city}")
            return {"cafes": [], "city": city}

        # Add city info to each cafe
        for cafe in cafes:
            cafe["city"] = city
            cafe["cityReference"] = city_reference

        # Save output for review
        output_file = (
            self.pipeline_dir / f"step2_cafes_{city.replace(' ', '_').lower()}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cafes, f, indent=2)

        logger.info(f"Step 2 complete. Cafe list for {city} saved to {output_file}")
        return {"cafes": cafes, "city": city}

    async def step3_geocode_cafes(self, cafes: list[dict], city: str) -> dict:
        """Step 3: Add geocoding information to cafes.

        Args:
            cafes: List of cafe dictionaries
            city: City name for geocoding context

        Returns:
            Dictionary containing cafes with geocoding information
        """
        logger.info(f"Step 3: Geocoding {len(cafes)} cafes in {city}...")

        geocoded_cafes = []
        for cafe in cafes:
            try:
                # Get coordinates and place_id
                geocoding_result = await self.geocoding_client.get_coordinates(
                    cafe["cafeAddress"], city, cafe.get("cafeName")
                )

                if geocoding_result:
                    coordinates = geocoding_result
                    cafe["latitude"], cafe["longitude"] = coordinates

                geocoded_cafes.append(cafe)

            except Exception as e:
                logger.error(
                    f"Error geocoding cafe {cafe.get('cafeName', 'unknown')}: {e}"
                )
                # Still include cafe without geocoding
                geocoded_cafes.append(cafe)

        # Save output for review
        output_file = (
            self.pipeline_dir / f"step3_geocoded_{city.replace(' ', '_').lower()}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(geocoded_cafes, f, indent=2)

        logger.info(
            f"Step 3 complete. Geocoded cafes for {city} saved to {output_file}"
        )
        return {"geocoded_cafes": geocoded_cafes, "city": city}

    async def step4_enrich_cafe_details(self, cafes: list[dict], city: str) -> dict:
        logger.info(f"Step 4: Enriching {len(cafes)} cafes in {city}...")

        enriched_entries = []
        for cafe in cafes:
            # Find Place ID first
            place_id = await self.places_client.find_place_id(
                name=cafe.get("cafeName"),
                address=cafe.get("cafeAddress"),
                city=cafe.get("city"),
            )

            if not place_id:
                logger.warning(
                    f"Could not find Place ID for {cafe.get('cafeName', 'N/A')} at {cafe.get('cafeAddress', 'N/A')}. Skipping enrichment."
                )
                continue

            cafe["placeId"] = place_id

            # Now proceed with LLM enrichment using the cafe dict containing the placeId
            enriched_cafe_result = await self.llm_client.enrich_cafe_details(cafe)

            enriched_entries.extend(enriched_cafe_result.entries)

        # Create a single payload with all entries
        combined_payload = {
            "entries": [entry.model_dump() for entry in enriched_entries]
        }

        # Save output for review
        output_file = (
            self.pipeline_dir / f"step4_enriched_{city.replace(' ', '_').lower()}.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_payload, f, indent=2)

        logger.info(
            f"Step 4 complete. Enriched cafes for {city} saved to {output_file}"
        )
        return {"enriched_cafes": combined_payload, "city": city}

    def collect_all_cafe_files(self) -> list[dict]:
        """Helper method to collect all enriched cafe data files.

        Returns:
            List of all cafes from step4 output files
        """
        all_cafes = []
        for file in self.pipeline_dir.glob("step4_enriched_*.json"):
            with open(file, "r", encoding="utf-8") as f:
                cafes = json.load(f)
                all_cafes.extend(cafes)

        return all_cafes
