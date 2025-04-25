#!/usr/bin/env python
import asyncio
import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

from .pipeline import CafePipeline
from .utils.logging import setup_logger
from .config import LOG_LEVEL

logger = setup_logger(__name__, level=LOG_LEVEL)

def get_user_confirmation(message: str = "Continue to the next step?", skip_confirmations: bool = False) -> bool:
    """Get confirmation from user to continue.
    
    Args:
        message: Message to display to user
        skip_confirmations: Whether to skip confirmations and return True
    
    Returns:
        True if user confirms or skip_confirmations is True, False otherwise
    """
    if skip_confirmations:
        logger.info(f"{message} (Automatically confirmed)")
        return True
        
    while True:
        response = input(f"\n{message} (y/n): ").lower().strip()
        if response in ["y", "yes"]:
            return True
        elif response in ["n", "no"]:
            return False
        else:
            print("Please enter 'y' or 'n'.")

async def run_city_pipeline(pipeline: CafePipeline, city_info: Dict, skip_confirmations: bool = False) -> List[Dict]:
    """Run the pipeline for a single city.
    
    Args:
        pipeline: Initialized CafePipeline instance
        city_info: City information dictionary
        skip_confirmations: Whether to skip user confirmations
    
    Returns:
        List of enriched cafe dictionaries
    """
    city = city_info['city']
    cafes_needed = city_info['cafes_needed']
    city_id = city_info['city_id']
    
    # Step 2: Get cafes for city
    result = await pipeline.step2_get_cafes_for_city(city, cafes_needed, city_id)
    cafes = result["cafes"]
    
    print(f"\nStep 2 Complete: Retrieved {len(cafes)} cafes for {city}")
    print(f"Review the output at: {pipeline.pipeline_dir}/step2_cafes_{city.replace(' ', '_').lower()}.json")
    
    if not get_user_confirmation("Continue to geocoding?", skip_confirmations):
        logger.info("Pipeline stopped after Step 2")
        return []
    
    # Step 3: Geocode cafes
    result = await pipeline.step3_geocode_cafes(cafes, city)
    geocoded_cafes = result["geocoded_cafes"]
    
    print(f"\nStep 3 Complete: Geocoded {len(geocoded_cafes)} cafes in {city}")
    print(f"Review the output at: {pipeline.pipeline_dir}/step3_geocoded_{city.replace(' ', '_').lower()}.json")
    
    if not get_user_confirmation("Continue to enrichment?", skip_confirmations):
        logger.info("Pipeline stopped after Step 3")
        return []
    
    # Step 4: Enrich cafe details
    result = await pipeline.step4_enrich_cafe_details(geocoded_cafes, city)
    enriched_cafes = result["enriched_cafes"]
    
    print(f"\nStep 4 Complete: Enriched {len(enriched_cafes)} cafes in {city}")
    print(f"Review the output at: {pipeline.pipeline_dir}/step4_enriched_{city.replace(' ', '_').lower()}.json")
    
    return enriched_cafes

async def main():
    """Main entry point for running the pipeline."""
    parser = argparse.ArgumentParser(description="Run the cafe data collection pipeline with steps for review")
    
    parser.add_argument(
        "input_csv",
        help="Path to CSV file containing city data"
    )
    parser.add_argument(
        "city_mapping_json",
        help="Path to JSON file containing city ID mappings"
    )
    parser.add_argument(
        "--city",
        help="Process only this specific city (optional)"
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=range(1, 6),
        help="Start from this step (1-5)"
    )
    parser.add_argument(
        "--skip-confirmations",
        action="store_true",
        help="Skip user confirmations when running from a specific step"
    )
    parser.add_argument(
        "--contentful-output",
        help="Path for Contentful output file"
    )
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = CafePipeline(args.input_csv, args.city_mapping_json)
    step = args.step or 1
    skip_confirmations = args.skip_confirmations
    
    # Step 1: Load input data and create collection queue
    if step <= 1:
        result = pipeline.step1_load_input_data()
        collection_queue = result["collection_queue"]
        
        print(f"\nStep 1 Complete: Loaded data for {len(collection_queue)} cities")
        print(f"Review the output at: {pipeline.pipeline_dir}/step1_city_queue.json")
        
        if not get_user_confirmation("Continue to cafe retrieval?", skip_confirmations):
            logger.info("Pipeline stopped after Step 1")
            return
    else:
        # Load collection queue from file if starting from a later step
        with open(pipeline.pipeline_dir / "step1_city_queue.json", 'r') as f:
            collection_queue = json.load(f)
    
    # Filter queue for specific city if requested
    if args.city:
        collection_queue = [city for city in collection_queue if city['city'] == args.city]
        if not collection_queue:
            logger.error(f"City '{args.city}' not found in collection queue")
            return
    
    # Steps 2-4: Process cities one by one
    all_cafes = []
    
    if step <= 4:
        for city_info in collection_queue:
            print(f"\nProcessing city: {city_info['city']}")
            
            enriched_cafes = await run_city_pipeline(pipeline, city_info, skip_confirmations)
            all_cafes.extend(enriched_cafes)
            
            if city_info != collection_queue[-1]:
                if not get_user_confirmation("Continue to next city?", skip_confirmations):
                    logger.info("Pipeline stopped before processing all cities")
                    break
    else:
        # If starting from a later step, collect all existing enriched cafe files
        all_cafes = pipeline.collect_all_cafe_files()
        print(f"\nLoaded {len(all_cafes)} cafes from existing files")
    
    # Step 5: Export to Contentful
    if step <= 5 and all_cafes:
        if get_user_confirmation("Export data to Contentful format?", skip_confirmations):
            result = pipeline.step5_export_to_contentful(all_cafes, args.contentful_output)
            contentful_path = result["contentful_path"]
            
            print(f"\nStep 5 Complete: Exported {len(all_cafes)} cafes to Contentful format")
            print(f"Review the output at: {contentful_path}")
    
    print("\nPipeline execution complete!")

if __name__ == "__main__":
    asyncio.run(main()) 