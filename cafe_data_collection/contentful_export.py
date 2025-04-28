import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .utils.logging import setup_logger
from .schemas import CafeReview
from .config import (
    OUTPUT_DIR,
    CONTENTFUL_SPACE_ID,
    CONTENTFUL_ACCESS_TOKEN,
    INPUT_ENCODING
)

logger = setup_logger(__name__)

class ContentfulExporter:
    def __init__(self):
        """Initialize the Contentful exporter."""
        self.space_id = CONTENTFUL_SPACE_ID
        self.access_token = CONTENTFUL_ACCESS_TOKEN
        self.content_type_id = "cafeReview"  # Contentful content type ID
        
    def format_cafe_review(self, review: Dict) -> Dict:
        """Format a cafe review into Contentful's expected structure.
        
        Args:
            review: Dictionary containing cafe review data
        
        Returns:
            Dictionary formatted for Contentful import
        """
        return {
            "metadata": {
                "tags": []
            },
            "sys": {
                "space": {
                    "sys": {
                        "type": "Link",
                        "linkType": "Space",
                        "id": self.space_id
                    }
                },
                "type": "Entry",
                "contentType": {
                    "sys": {
                        "type": "Link",
                        "linkType": "ContentType",
                        "id": self.content_type_id
                    }
                }
            },
            "fields": {
                "cafeName": {
                    "en-US": review["cafeName"]
                },
                "authorName": {
                    "en-US": review.get("authorName", "Cafe Data Collection")
                },
                "publishDate": {
                    "en-US": datetime.now().isoformat()
                },
                "slug": {
                    "en-US": review.get("slug", review["cafeName"].lower().replace(" ", "-"))
                },
                "excerpt": {
                    "en-US": review.get("excerpt", "")
                },
                "instagramLink": {
                    "en-US": review.get("instagramLink", None)
                },
                "facebookLink": {
                    "en-US": review.get("facebookLink", None)
                },
                "overallScore": {
                    "en-US": review.get("overallScore", 0)
                },
                "coffeeScore": {
                    "en-US": review.get("coffeeScore", 0)
                },
                "atmosphereScore": {
                    "en-US": review.get("atmosphereScore", 0)
                },
                "serviceScore": {
                    "en-US": review.get("serviceScore", 0)
                },
                "valueScore": {
                    "en-US": review.get("valueScore", 0)
                },
                "foodScore": {
                    "en-US": review.get("foodScore", 0)
                },
                "vibeScore": {
                    "en-US": review.get("vibeScore", 0)
                },
                "vibeDescription": {
                    "en-US": review.get("vibeDescription", {})
                },
                "theStory": {
                    "en-US": review.get("theStory", {})
                },
                "craftExpertise": {
                    "en-US": review.get("craftExpertise", {})
                },
                "setsApart": {
                    "en-US": review.get("setsApart", {})
                },
                "cafeAddress": {
                    "en-US": review.get("cafeAddress", "")
                },
                "cityReference": {
                    "en-US": {
                        "sys": {
                            "type": "Link",
                            "linkType": "Entry",
                            "id": review.get("cityId", "")
                        }
                    }
                },
                "cafeLatLon": {
                    "en-US": {
                        "lat": review.get("latitude", 0),
                        "lon": review.get("longitude", 0)
                    } if "latitude" in review and "longitude" in review else None
                },
                "placeId": {
                    "en-US": review.get("placeId", "")
                }
            }
        }
    
    def export_reviews(self, reviews: List[Dict], output_file: Optional[str] = None) -> str:
        """Export cafe reviews to a file in Contentful format.
        
        Args:
            reviews: List of cafe review dictionaries to export
            output_file: Optional output file path (default: contentful_export_{timestamp}.json)
            
        Returns:
            Path to the output file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"contentful_export_{timestamp}.json"
        else:
            output_file = Path(output_file)
        
        # Create output directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Format all reviews
        formatted_reviews = []
        for review in reviews:
            try:
                formatted = self.format_cafe_review(review)
                formatted_reviews.append(formatted)
            except Exception as e:
                logger.error(f"Error formatting review for {review.get('cafeName', 'unknown cafe')}: {e}")
                continue
        
        # Create the export structure
        export_data = {
            "version": 7,
            "entries": formatted_reviews
        }
        
        # Write to file
        try:
            with open(output_file, 'w', encoding=INPUT_ENCODING) as f:
                json.dump(export_data, f, indent=2)
            logger.info(f"Exported {len(formatted_reviews)} reviews to {output_file}")
            return str(output_file)
        except Exception as e:
            logger.error(f"Error writing export file: {e}")
            raise 