import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional

from .utils.logging import setup_logger
from .data_collection import DataCollector
from .llm_client import LLMClient
from .geocoding import GeocodingClient
from .contentful_export import ContentfulExporter
from .config import (
    LOG_LEVEL,
    INPUT_ENCODING
)

logger = setup_logger(__name__, level=getattr(logging, LOG_LEVEL))

async def run_collection(
    input_csv: str,
    city_mapping_json: str,
    export_contentful: bool = True,
    contentful_output: Optional[str] = None
) -> None:
    """Run the cafe data collection process.
    
    Args:
        input_csv: Path to CSV file with city data
        city_mapping_json: Path to JSON file with city ID mappings
        export_contentful: Whether to export to Contentful format
        contentful_output: Optional path for Contentful output
    """
    try:
        # Initialize components
        collector = DataCollector(input_csv, city_mapping_json)
        llm_client = LLMClient()
        geocoding_client = GeocodingClient()
        
        # Load input data
        collector.load_input_data()
        collection_queue = collector.get_collection_queue()
        
        # Get existing progress
        progress = collector.get_collection_progress()
        
        # Process each city
        all_reviews = []
        for city_info in collection_queue:
            city = city_info['city']
            cafes_needed = city_info['cafes_needed']
            cafes_collected = progress.get(city, 0)
            
            if cafes_collected >= cafes_needed:
                logger.info(f"Skipping {city} - already collected {cafes_collected} cafes")
                continue
            
            logger.info(f"Processing {city} - need {cafes_needed} cafes, have {cafes_collected}")
            
            # Get cafe list from LLM
            cafes = await llm_client.get_cafes_for_city(city, cafes_needed - cafes_collected)
            
            # Process each cafe
            for cafe in cafes:
                try:
                    # Get coordinates
                    coordinates = await geocoding_client.get_coordinates(
                        cafe['cafeAddress'],
                        city
                    )
                    if coordinates:
                        cafe['latitude'], cafe['longitude'] = coordinates
                    
                    # Enrich with details
                    enriched = await llm_client.enrich_cafe_details({
                        **cafe,
                        'city': city,
                        'cityId': city_info['city_id']
                    })
                    
                    all_reviews.append(enriched)
                    
                    # Update progress
                    progress[city] = progress.get(city, 0) + 1
                    collector.save_collection_progress(progress)
                    
                except Exception as e:
                    logger.error(f"Error processing cafe {cafe.get('cafeName', 'unknown')}: {e}")
                    continue
        
        # Export results
        if all_reviews:
            if export_contentful:
                contentful_exporter = ContentfulExporter()
                contentful_exporter.export_reviews(all_reviews, contentful_output)
                logger.info(f"Exported reviews to Contentful format")
        else:
            logger.warning("No reviews collected")
            
    except Exception as e:
        logger.error(f"Error during collection process: {e}")
        raise

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Collect cafe data and generate reviews")
    
    parser.add_argument(
        "input_csv",
        help="Path to CSV file containing city data"
    )
    parser.add_argument(
        "city_mapping_json",
        help="Path to JSON file containing city ID mappings"
    )
    parser.add_argument(
        "--no-contentful",
        action="store_false",
        dest="export_contentful",
        help="Skip Contentful export"
    )
    parser.add_argument(
        "--contentful-output",
        help="Path for Contentful output file"
    )
    
    args = parser.parse_args()
    
    # Run the collection process
    asyncio.run(run_collection(
        args.input_csv,
        args.city_mapping_json,
        args.export_contentful,
        args.contentful_output
    ))

if __name__ == "__main__":
    main() 