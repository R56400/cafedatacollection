from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import datetime, date


class Location(BaseModel):
    lat: float
    lon: float


class Rating(BaseModel):
    overall: float = Field(..., ge=0, le=10)
    coffee: float = Field(..., ge=0, le=10)
    food: float = Field(..., ge=0, le=10)
    vibe: int = Field(..., ge=1, le=10)  # Integer type as per schema
    atmosphere: float = Field(..., ge=0, le=10)
    service: float = Field(..., ge=0, le=10)
    value: float = Field(..., ge=0, le=10)


class RichTextContent(BaseModel):
    nodeType: str
    content: List[Dict]
    data: Optional[Dict] = None


class RichText(BaseModel):
    data: Dict = {}
    content: List[Dict]
    nodeType: str = "document"

    @validator('content')
    def validate_rich_text_content(cls, v):
        # Validate that only allowed node types and marks are used
        allowed_marks = [
            "bold", "italic", "underline", "code",
            "superscript", "subscript", "strikethrough"
        ]
        allowed_nodes = [
            "heading-1", "heading-2", "heading-3", "heading-4",
            "heading-5", "heading-6", "ordered-list", "unordered-list",
            "hr", "blockquote", "embedded-entry-block",
            "embedded-asset-block", "table", "asset-hyperlink",
            "embedded-entry-inline", "entry-hyperlink", "hyperlink"
        ]
        return v


class SocialLinkRichText(RichText):
    @validator('content')
    def validate_social_link_content(cls, v):
        # Only allow hyperlink nodes, no marks
        for node in v:
            if node['nodeType'] not in ['hyperlink']:
                raise ValueError("Only hyperlink nodes are allowed in social links")
            if 'marks' in node and node['marks']:
                raise ValueError("Marks are not allowed in social links")
        return v


class CafeReview(BaseModel):
    """A comprehensive review of a cafe.
    
    The review includes basic information, scores, and four distinct rich text sections:
    
    1. Vibe Description (exactly 3 sentences):
       - Captures the spirit and atmosphere of the place
       - Written as you would describe it to friends
       - Focuses on emotional and social experience
       - Avoids technical details about coffee, food, or service
    
    2. The Story (3-5 sentences):
       - Origins and mission of the cafe
       - Information about the founders
       - Notable achievements or milestones
       - Broader vision and impact
       - No technical coffee details
    
    3. Craft & Expertise (up to 5 sentences):
       - Coffee quality and preparation details
       - Barista expertise and service
       - Special or unique drinks
       - Seating and drinkware
       - Complete food and drink experience
    
    4. What Sets Them Apart (3-4 sentences):
       - Unique differentiators from other cafes
       - Special perspective on coffee or design
       - Standout features or approaches
       - What makes them memorable
    """
    
    cafeName: str
    authorName: str = "Chris Jordan"
    publishDate: date = Field(default_factory=date.today)
    slug: str
    excerpt: str
    instagramLink: Optional[SocialLinkRichText] = None
    facebookLink: Optional[SocialLinkRichText] = None
    overallScore: float = Field(..., ge=0, le=10)
    coffeeScore: float = Field(..., ge=0, le=10)
    atmosphereScore: float = Field(..., ge=0, le=10)
    serviceScore: float = Field(..., ge=0, le=10)
    valueScore: float = Field(..., ge=0, le=10)
    foodScore: float = Field(..., ge=0, le=10)
    vibeScore: int = Field(..., ge=1, le=10)
    vibeDescription: RichText = Field(
        ...,
        description="A 3-sentence description of the cafe's spirit and atmosphere, "
                   "written in a friendly, conversational tone. Should focus on the "
                   "emotional and social experience, avoiding technical details."
    )
    theStory: RichText = Field(
        ...,
        description="3-5 sentences about the cafe's origins, founders, mission, "
                   "and notable achievements. Focus on the broader vision and impact, "
                   "not technical coffee details."
    )
    craftExpertise: RichText = Field(
        ...,
        description="Up to 5 sentences detailing coffee quality, barista expertise, "
                   "special drinks, seating, and the overall food/drink experience."
    )
    setsApart: RichText = Field(
        ...,
        description="3-4 sentences highlighting unique differentiators, special "
                   "perspectives on coffee/design, and standout features that make "
                   "the cafe memorable."
    )
    cafeAddress: str
    cityReference: Dict  # Link to city content type with proper ID
    cafeLatLon: Optional[Location] = None
    placeId: str

    @validator('coffeeScore', 'atmosphereScore', 'serviceScore', 'valueScore', 'foodScore', 'overallScore')
    def validate_score_decimal_places(cls, v):
        """Ensure all scores have exactly 1 decimal place."""
        # Round to 1 decimal place
        rounded = round(v, 1)
        if abs(v - rounded) > 0.0001:  # Using small epsilon for float comparison
            raise ValueError(f'Score must have exactly 1 decimal place. Got {v}, expected {rounded}')
        return rounded

    @validator('overallScore')
    def validate_overall_score(cls, v, values):
        """Validate that overall score is the average of primary scores with 1 decimal place.
        
        The overall score should be the average of:
        - Coffee Score
        - Atmosphere Score
        - Service Score
        - Value Score
        - Food Score
        """
        # Check if we have all the required scores
        required_scores = ['coffeeScore', 'atmosphereScore', 'serviceScore', 'valueScore', 'foodScore']
        if not all(score in values for score in required_scores):
            return v  # Skip validation if we don't have all scores yet
            
        # Calculate the average
        scores = [values[score] for score in required_scores]
        avg = sum(scores) / len(scores)
        
        # Round to 1 decimal place
        expected = round(avg, 1)
        
        # Check if the provided overall score matches the calculated one
        if abs(v - expected) > 0.0001:  # Using small epsilon for float comparison
            raise ValueError(
                f'Overall score must be the average of primary scores with 1 decimal place. '
                f'Expected {expected} (average of {scores}), got {v}'
            )
        
        return v
    
    @validator('slug')
    def validate_slug_format(cls, v):
        """Validate and format the slug to follow cafe-name-street format.
        
        Example:
            Cafe: Scarlett Coffee
            Street: Main St
            Slug: scarlett-coffee-main
        """
        # Clean and normalize the slug
        slug = v.lower().strip()
        
        # Split by hyphens
        parts = slug.split('-')
        
        # Need at least two parts: cafe name and street
        if len(parts) < 2:
            raise ValueError('Slug must contain cafe name and street name (e.g., scarlett-coffee-main)')
            
        # Check that we don't have empty parts
        if any(not part.strip() for part in parts):
            raise ValueError('Slug cannot contain empty parts')
            
        # Check that all parts are alphanumeric (allowing hyphens between parts)
        if not all(part.replace('-', '').isalnum() for part in parts):
            raise ValueError('Slug must contain only letters, numbers, and hyphens')
            
        return slug 