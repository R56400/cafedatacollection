import json
import time

import httpx

from .config import GOOGLE_MAPS_API_KEY, RATE_LIMITS
from .utils.logging import setup_logger

logger = setup_logger(__name__)


class PlacesClient:
    def __init__(self):
        """Initialize the Places API client."""
        self.api_key = GOOGLE_MAPS_API_KEY
        # Use the v1 endpoint for Text Search (New)
        self.base_url = "https://places.googleapis.com/v1/places:searchText"
        self.last_request_time = 0
        # Assume a separate rate limit for Places API, key needs adding to config
        self.rate_limit_key = "google_places"

    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed the rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        # Get the specific rate limit for Places API
        limit_per_minute = RATE_LIMITS.get(self.rate_limit_key)
        if not limit_per_minute:
            logger.warning(
                f"Rate limit for '{self.rate_limit_key}' not found in config. Skipping rate limit."
            )
            self.last_request_time = current_time
            return

        min_interval = 60.0 / limit_per_minute

        if elapsed < min_interval:
            sleep_duration = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_duration:.2f} seconds.")
            time.sleep(sleep_duration)

        self.last_request_time = time.time()

    async def find_place_id(
        self, name: str, address: str | None, city: str | None
    ) -> str | None:
        """
        Find the Google Place ID for a cafe using Text Search.

        Args:
            name: The name of the cafe.
            address: The street address (optional but recommended).
            city: The city (optional but recommended).

        Returns:
            The Place ID string if found, otherwise None.
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured for Places API.")
            return None

        # Construct a query prioritizing name, address, and city
        query_parts = filter(None, [name, address, city])
        text_query = ", ".join(query_parts)

        if not text_query:
            logger.warning("Cannot search for place ID with empty query.")
            return None

        # Respect rate limit
        self._respect_rate_limit()

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id",  # Request only the place ID
        }

        payload = json.dumps({"textQuery": text_query})

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Searching Place ID for: {text_query}")
                response = await client.post(
                    self.base_url, headers=headers, content=payload
                )
                response.raise_for_status()

                data = response.json()

                # Extract the first place ID if available
                places = data.get("places", [])
                if places and isinstance(places, list) and "id" in places[0]:
                    place_id = places[0]["id"]
                    logger.debug(f"Found Place ID: {place_id} for query: {text_query}")
                    return place_id
                else:
                    logger.warning(
                        f"No Place ID found for query: {text_query}. Response: {data}"
                    )
                    return None

        except httpx.RequestError as e:
            logger.error(f"HTTP error finding Place ID for '{text_query}': {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP status error finding Place ID for '{text_query}': {e.response.status_code} - {e.response.text}"
            )
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON response for '{text_query}'.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error finding Place ID for '{text_query}': {e}")
            return None
