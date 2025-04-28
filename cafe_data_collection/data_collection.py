import json
from pathlib import Path

import pandas as pd

from .config import INPUT_ENCODING
from .utils.logging import setup_logger

logger = setup_logger(__name__)


class DataCollector:
    def __init__(self, input_csv: Path, city_mapping_json: Path):
        """Initialize the data collector.

        Args:
            input_csv: Path to CSV file with city data
            city_mapping_json: Path to JSON file with city ID mappings
        """
        self.input_csv = Path(input_csv)
        self.city_mapping_json = Path(city_mapping_json)
        self.cities_data = None
        self.city_mappings = None

    def load_input_data(self) -> None:
        """Load and validate input data from CSV and JSON files."""
        try:
            # Load CSV data
            self.cities_data = pd.read_csv(self.input_csv, encoding=INPUT_ENCODING)

            # Validate CSV columns
            required_columns = {"City", "Cafes Needed"}
            if not all(col in self.cities_data.columns for col in required_columns):
                raise ValueError(f"CSV must contain columns: {required_columns}")

            # Load city mappings
            with open(self.city_mapping_json, "r", encoding=INPUT_ENCODING) as f:
                self.city_mappings = json.load(f)

            logger.info(f"Loaded data for {len(self.cities_data)} cities")

        except FileNotFoundError as e:
            logger.error(f"Input file not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading input data: {e}")
            raise

    def get_collection_queue(self) -> list[dict]:
        """Create a prioritized queue of cities to process.

        Returns:
            List of dictionaries containing city information and number of cafes needed
        """
        if self.cities_data is None:
            raise ValueError("Input data not loaded. Call load_input_data() first")

        # Create queue sorted by number of cafes needed (descending)
        queue = []
        for _, row in self.cities_data.sort_values(
            "Cafes Needed", ascending=False
        ).iterrows():
            city = row["City"]

            # Get city ID from mapping
            city_id = self.city_mappings.get(city)
            if not city_id:
                logger.warning(f"No mapping found for city: {city}")
                continue

            queue.append(
                {
                    "city": city,
                    "cafes_needed": int(row["Cafes Needed"]),
                    "city_id": city_id,
                }
            )

        return queue
