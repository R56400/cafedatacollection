import time

import httpx

from .config import GOOGLE_MAPS_API_KEY, RATE_LIMITS
from .utils.logging import setup_logger

logger = setup_logger(__name__)


class GeocodingClient:
    def __init__(self):
        """Initialize the geocoding client."""
        self.api_key = GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.last_request_time = 0

    def _respect_rate_limit(self) -> None:
        """Ensure we don't exceed the rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time

        # Convert rate limit to seconds
        min_interval = 60.0 / RATE_LIMITS["google_maps"]

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self.last_request_time = time.time()

    async def get_coordinates(
        self, address: str, city: str
    ) -> tuple[float, float] | None:
        """Get latitude and longitude for a given address.

        Args:
            address: Street address of the cafe
            city: City name to improve geocoding accuracy

        Returns:
            Tuple of (latitude, longitude) if found, None otherwise
        """
        if not self.api_key:
            logger.warning("Google Maps API key not configured")
            return None

        # Combine address and city for better accuracy
        full_address = f"{address}, {city}"

        # Respect rate limit
        self._respect_rate_limit()

        try:
            async with httpx.AsyncClient() as client:
                params = {"address": full_address, "key": self.api_key}

                response = await client.get(self.base_url, params=params)
                response.raise_for_status()

                data = response.json()

                if data["status"] == "OK" and data["results"]:
                    location = data["results"][0]["geometry"]["location"]
                    coordinates = (location["lat"], location["lng"])

                    return coordinates
                else:
                    logger.warning(f"No coordinates found for address: {full_address}")
                    return None

        except httpx.RequestError as e:
            logger.error(f"Error geocoding address {full_address}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error geocoding address {full_address}: {e}")
            return None
