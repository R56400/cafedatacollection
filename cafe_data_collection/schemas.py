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


class CafeReview(BaseModel):
    cafeName: str
    authorName: str = "Chris Jordan"
    publishDate: date = Field(default_factory=date.today)
    slug: str
    excerpt: str
    overallScore: float = Field(..., ge=0, le=10)
    coffeeScore: float = Field(..., ge=0, le=10)
    atmosphereScore: float = Field(..., ge=0, le=10)
    serviceScore: float = Field(..., ge=0, le=10)
    valueScore: float = Field(..., ge=0, le=10)
    foodScore: float = Field(..., ge=0, le=10)
    vibeScore: int = Field(..., ge=1, le=10)
    vibeDescription: RichText
    theStory: RichText
    craftExpertise: RichText
    setsApart: RichText
    cafeAddress: str
    cityReference: Dict  # Link to city content type with proper ID
    cafeLatLon: Optional[Location] = None
    instagramLink: Optional[RichText] = None
    facebookLink: Optional[RichText] = None
    
    @validator('slug')
    def validate_slug_format(cls, v):
        # Ensure slug follows the cafe-name-street-city format
        parts = v.split('-')
        if len(parts) < 3:
            raise ValueError('Slug must contain cafe name, street name, and city')
        return v 