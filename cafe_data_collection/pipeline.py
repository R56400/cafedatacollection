import asyncio
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional

from .utils.logging import setup_logger
from .data_collection import DataCollector
from .llm_client import LLMClient
from .geocoding import GeocodingClient
from .contentful_export import ContentfulExporter
from .excel_export import ExcelExporter
from .config import (
    LOG_LEVEL,
    INPUT_ENCODING,
    OUTPUT_DIR
)

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
        
    def step1_load_input_data(self) -> Dict:
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
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(collection_queue, f, indent=2)
        
        logger.info(f"Step 1 complete. City queue saved to {output_file}")
        return {"collection_queue": collection_queue}
    
    async def step2_get_cafes_for_city(self, city: str, cafes_needed: int, city_id: str) -> Dict:
        """Step 2: Get a list of cafes for a specific city.
        
        Args:
            city: Name of the city
            cafes_needed: Number of cafes to retrieve
            city_id: City ID from mapping file
            
        Returns:
            Dictionary containing the list of cafes
        """
        logger.info(f"Step 2: Getting cafes for {city} (need {cafes_needed})...")
        
        # Get cafe list from LLM
        cafes = await self.llm_client.get_cafes_for_city(city, cafes_needed)
        
        # Add city info to each cafe and ensure field names match template
        for cafe in cafes:
            cafe['city'] = city
            cafe['cityId'] = city_id
            
            # Convert briefDescription to excerpt if needed
            if 'briefDescription' in cafe and 'excerpt' not in cafe:
                cafe['excerpt'] = cafe.pop('briefDescription')
            
            # Ensure verification source exists
            if 'verificationSource' not in cafe:
                logger.warning(f"Missing verification source for cafe: {cafe['cafeName']}")
                cafe['verificationSource'] = "Verification source not provided"
        
        # Save output for review
        output_file = self.pipeline_dir / f"step2_cafes_{city.replace(' ', '_').lower()}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cafes, f, indent=2)
        
        logger.info(f"Step 2 complete. Cafe list for {city} saved to {output_file}")
        return {"cafes": cafes, "city": city}
    
    async def step3_geocode_cafes(self, cafes: List[Dict], city: str) -> Dict:
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
                # Get coordinates
                coordinates = await self.geocoding_client.get_coordinates(
                    cafe['cafeAddress'],
                    city
                )
                
                if coordinates:
                    cafe['latitude'], cafe['longitude'] = coordinates
                
                geocoded_cafes.append(cafe)
                
            except Exception as e:
                logger.error(f"Error geocoding cafe {cafe.get('cafeName', 'unknown')}: {e}")
                # Still include cafe without geocoding
                geocoded_cafes.append(cafe)
        
        # Save output for review
        output_file = self.pipeline_dir / f"step3_geocoded_{city.replace(' ', '_').lower()}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geocoded_cafes, f, indent=2)
        
        logger.info(f"Step 3 complete. Geocoded cafes for {city} saved to {output_file}")
        return {"geocoded_cafes": geocoded_cafes, "city": city}
    
    async def step4_enrich_cafe_details(self, cafes: List[Dict], city: str) -> Dict:
        """Step 4: Enrich cafes with detailed content.
        
        Args:
            cafes: List of cafe dictionaries
            city: City name for context
            
        Returns:
            Dictionary containing enriched cafe details
        """
        logger.info(f"Step 4: Enriching {len(cafes)} cafes in {city}...")
        
        enriched_cafes = []
        for cafe in cafes:
            try:
                # Enrich with details
                enriched = await self.llm_client.enrich_cafe_details(cafe)
                enriched_cafes.append(enriched)
                
            except Exception as e:
                logger.error(f"Error enriching cafe {cafe.get('cafeName', 'unknown')}: {e}")
                # Include original cafe if enrichment fails
                enriched_cafes.append(cafe)
        
        # Save output for review
        output_file = self.pipeline_dir / f"step4_enriched_{city.replace(' ', '_').lower()}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_cafes, f, indent=2)
        
        logger.info(f"Step 4 complete. Enriched cafes for {city} saved to {output_file}")
        return {"enriched_cafes": enriched_cafes, "city": city}
    
    def step5_export_to_excel(self, all_cafes: List[Dict], output_path: Optional[str] = None) -> Dict:
        """Step 5: Export all cafes to Excel format.
        
        Args:
            all_cafes: List of all cafe dictionaries
            output_path: Optional custom path for Excel output
            
        Returns:
            Dictionary containing export result information
        """
        logger.info(f"Step 5: Exporting {len(all_cafes)} cafes to Excel...")
        
        excel_exporter = ExcelExporter()
        excel_path = excel_exporter.export_reviews(all_cafes, output_path)
        
        logger.info(f"Step 5 complete. Excel export saved to {excel_path}")
        return {"excel_path": excel_path}
    
    def step6_export_to_contentful(self, all_cafes: List[Dict], output_path: Optional[str] = None) -> Dict:
        """Step 6: Export all cafes to Contentful format.
        
        Args:
            all_cafes: List of all cafe dictionaries
            output_path: Optional custom path for Contentful output
            
        Returns:
            Dictionary containing export result information
        """
        logger.info(f"Step 6: Exporting {len(all_cafes)} cafes to Contentful format...")
        
        contentful_exporter = ContentfulExporter()
        contentful_path = contentful_exporter.export_reviews(all_cafes, output_path)
        
        logger.info(f"Step 6 complete. Contentful export saved to {contentful_path}")
        return {"contentful_path": contentful_path}
    
    def collect_all_cafe_files(self) -> List[Dict]:
        """Helper method to collect all enriched cafe data files.
        
        Returns:
            List of all cafes from step4 output files
        """
        all_cafes = []
        for file in self.pipeline_dir.glob("step4_enriched_*.json"):
            with open(file, 'r', encoding='utf-8') as f:
                cafes = json.load(f)
                all_cafes.extend(cafes)
        
        return all_cafes 