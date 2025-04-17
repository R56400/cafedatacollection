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
        
    def format_cafe_review(self, review: CafeReview) -> Dict:
        """Format a cafe review into Contentful's expected structure.
        
        Args:
            review: CafeReview instance to format
        
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
                    "en-US": review.cafeName
                },
                "authorName": {
                    "en-US": review.authorName
                },
                "publishDate": {
                    "en-US": review.publishDate.isoformat()
                },
                "slug": {
                    "en-US": review.slug
                },
                "excerpt": {
                    "en-US": review.excerpt
                },
                "instagramLink": {
                    "en-US": review.instagramLink.dict() if review.instagramLink else None
                },
                "facebookLink": {
                    "en-US": review.facebookLink.dict() if review.facebookLink else None
                },
                "overallScore": {
                    "en-US": review.overallScore
                },
                "coffeeScore": {
                    "en-US": review.coffeeScore
                },
                "atmosphereScore": {
                    "en-US": review.atmosphereScore
                },
                "serviceScore": {
                    "en-US": review.serviceScore
                },
                "valueScore": {
                    "en-US": review.valueScore
                },
                "foodScore": {
                    "en-US": review.foodScore
                },
                "vibeScore": {
                    "en-US": review.vibeScore
                },
                "vibeDescription": {
                    "en-US": review.vibeDescription.dict()
                },
                "theStory": {
                    "en-US": review.theStory.dict()
                },
                "craftExpertise": {
                    "en-US": review.craftExpertise.dict()
                },
                "setsApart": {
                    "en-US": review.setsApart.dict()
                },
                "cafeAddress": {
                    "en-US": review.cafeAddress
                },
                "cityReference": {
                    "en-US": {
                        "sys": {
                            "type": "Link",
                            "linkType": "Entry",
                            "id": review.cityReference["id"]
                        }
                    }
                },
                "cafeLatLon": {
                    "en-US": {
                        "lat": review.cafeLatLon.lat,
                        "lon": review.cafeLatLon.lon
                    } if review.cafeLatLon else None
                },
                "placeId": {
                    "en-US": review.placeId
                }
            }
        }
    
    def export_reviews(self, reviews: List[CafeReview], output_file: Optional[str] = None) -> None:
        """Export cafe reviews to a file in Contentful format.
        
        Args:
            reviews: List of CafeReview instances to export
            output_file: Optional output file path (default: contentful_export_{timestamp}.json)
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
                logger.error(f"Error formatting review for {review.cafeName}: {e}")
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
        except Exception as e:
            logger.error(f"Error writing export file: {e}")
            raise 