import pandas as pd
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from .utils.logging import setup_logger
from .schemas import CafeReview
from .config import (
    OUTPUT_DIR,
    INPUT_ENCODING
)

logger = setup_logger(__name__)

class ExcelExporter:
    def __init__(self):
        """Initialize the Excel exporter."""
        pass
    
    def _flatten_review(self, review: CafeReview) -> Dict:
        """Flatten a CafeReview instance into a dictionary for Excel.
        
        Args:
            review: CafeReview instance to flatten
        
        Returns:
            Dictionary with flattened review data
        """
        # Helper function to extract text from rich text
        def get_rich_text_content(rich_text: Dict) -> str:
            try:
                # Extract text from all paragraph nodes
                texts = []
                for content in rich_text['content']:
                    if content['nodeType'] == 'paragraph':
                        for text_node in content['content']:
                            if text_node['nodeType'] == 'text':
                                texts.append(text_node['value'])
                return ' '.join(texts)
            except (KeyError, TypeError):
                return ''
        
        # Helper function to extract URL from social link
        def get_social_link_url(rich_text: Optional[Dict]) -> str:
            if not rich_text:
                return ''
            try:
                for content in rich_text['content']:
                    if content['nodeType'] == 'hyperlink':
                        return content['data']['uri']
                return ''
            except (KeyError, TypeError):
                return ''
        
        return {
            'Cafe Name': review.cafeName,
            'Author': review.authorName,
            'Publish Date': review.publishDate,
            'Slug': review.slug,
            'Excerpt': review.excerpt,
            'Instagram Link': get_social_link_url(review.instagramLink.dict() if review.instagramLink else None),
            'Facebook Link': get_social_link_url(review.facebookLink.dict() if review.facebookLink else None),
            'Overall Score': review.overallScore,
            'Coffee Score': review.coffeeScore,
            'Food Score': review.foodScore,
            'Vibe Score': review.vibeScore,
            'Atmosphere Score': review.atmosphereScore,
            'Service Score': review.serviceScore,
            'Value Score': review.valueScore,
            'Address': review.cafeAddress,
            'City ID': review.cityReference.get('id', ''),
            'Latitude': review.cafeLatLon.lat if review.cafeLatLon else '',
            'Longitude': review.cafeLatLon.lon if review.cafeLatLon else '',
            'Place ID': review.placeId,
            'Vibe Description': get_rich_text_content(review.vibeDescription.dict()),
            'The Story': get_rich_text_content(review.theStory.dict()),
            'Craft & Expertise': get_rich_text_content(review.craftExpertise.dict()),
            'Sets Apart': get_rich_text_content(review.setsApart.dict())
        }
    
    def export_reviews(self, reviews: List[CafeReview], output_file: Optional[str] = None) -> str:
        """Export cafe reviews to Excel for review.
        
        Args:
            reviews: List of CafeReview instances to export
            output_file: Optional output file path (default: cafe_reviews_{timestamp}.xlsx)
        
        Returns:
            Path to the created Excel file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = OUTPUT_DIR / f"cafe_reviews_{timestamp}.xlsx"
        else:
            output_file = Path(output_file)
        
        # Create output directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Flatten all reviews
        flattened_reviews = []
        for review in reviews:
            try:
                flat_review = self._flatten_review(review)
                flattened_reviews.append(flat_review)
            except Exception as e:
                logger.error(f"Error flattening review for {review.cafeName}: {e}")
                continue
        
        # Convert to DataFrame
        df = pd.DataFrame(flattened_reviews)
        
        # Reorder columns for better readability
        column_order = [
            'Cafe Name',
            'Address',
            'City ID',
            'Place ID',
            'Latitude',
            'Longitude',
            'Slug',
            'Author',
            'Publish Date',
            'Excerpt',
            'Instagram Link',
            'Facebook Link',
            'Overall Score',
            'Coffee Score',
            'Food Score',
            'Vibe Score',
            'Atmosphere Score',
            'Service Score',
            'Value Score',
            'Vibe Description',
            'The Story',
            'Craft & Expertise',
            'Sets Apart'
        ]
        df = df[column_order]
        
        # Export to Excel
        try:
            writer = pd.ExcelWriter(output_file, engine='openpyxl')
            df.to_excel(writer, index=False, sheet_name='Cafe Reviews')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Cafe Reviews']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
            
            writer.close()
            logger.info(f"Exported {len(reviews)} reviews to {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"Error writing Excel file: {e}")
            raise
    
    def import_reviews(self, excel_file: str) -> List[Dict]:
        """Import and validate reviews from Excel file.
        
        Args:
            excel_file: Path to Excel file containing reviews
        
        Returns:
            List of dictionaries containing review data
        """
        try:
            df = pd.read_excel(excel_file)
            reviews = df.to_dict('records')
            logger.info(f"Imported {len(reviews)} reviews from {excel_file}")
            return reviews
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            raise 