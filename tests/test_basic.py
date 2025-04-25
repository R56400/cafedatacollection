import os
import sys
import unittest
from pathlib import Path

# Add parent directory to path to import package
sys.path.insert(0, str(Path(__file__).parent.parent))

from cafe_data_collection import (
    DataCollector,
    LLMClient,
    GeocodingClient,
    ContentfulExporter
)
from cafe_data_collection.schemas import CafeReview

class TestBasicFunctionality(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.example_dir = Path(__file__).parent.parent / 'examples'
        self.input_csv = self.example_dir / 'input.csv'
        self.city_mapping = self.example_dir / 'city_mappings.json'
    
    def test_imports(self):
        """Test that all main components can be imported."""
        self.assertIsNotNone(DataCollector)
        self.assertIsNotNone(LLMClient)
        self.assertIsNotNone(GeocodingClient)
        self.assertIsNotNone(ContentfulExporter)
    
    def test_data_collector_initialization(self):
        """Test that DataCollector can be initialized with example files."""
        collector = DataCollector(self.input_csv, self.city_mapping)
        self.assertIsNotNone(collector)
    
    def test_input_file_loading(self):
        """Test that example input files can be loaded."""
        collector = DataCollector(self.input_csv, self.city_mapping)
        collector.load_input_data()
        
        # Get collection queue and verify cities
        queue = collector.get_collection_queue()
        self.assertTrue(len(queue) > 0)
        
        # Verify some expected cities are in the queue
        cities = {item['city'] for item in queue}
        expected_cities = {'San Francisco', 'New York', 'Los Angeles'}
        self.assertTrue(all(city in cities for city in expected_cities))
    
    def test_cafe_review_model(self):
        """Test that CafeReview model validation works."""
        with self.assertRaises(ValueError):
            # Should raise error due to missing required fields
            CafeReview()
    
if __name__ == '__main__':
    unittest.main() 