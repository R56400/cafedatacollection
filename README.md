# Cafe Data Collection

## Overview
This is a project aimed at creating a Python script to help collect cafe and coffee shop names, and then pass them through an LLM API to generate data that we'll fill into a large table/database that we can then upload through a Contentful API.

# Cafe Data Collection System Project Plan

## 1. Project Overview
A Python system to collect, process, and store coffee shop data across multiple cities using Large Language Models (LLMs), with built-in caching, error handling, and schema validation conforming to the provided Contentful schema.

## 2. Project Structure
```
cafe_data_collection/
├── .env                    # API keys and configuration
├── requirements.txt        # Dependencies
├── main.py                 # Entry point
├── config.py               # Configuration settings
├── llm_client.py           # LLM API interaction
├── data_collection.py      # Coffee shop collection functions
├── data_enrichment.py      # Adding ratings and details
├── storage.py              # Data persistence functions
├── schemas.py              # Pydantic models for validation
├── contentful_export.py    # Format JSON for Contentful
├── excel_export.py         # Export to Excel for review
├── utils/
│   ├── caching.py          # Caching system
│   ├── error_handling.py   # API error handlers
│   ├── text_generation.py  # Specialized text generation
│   ├── slug_generation.py  # Custom slug generator
│   └── logging.py          # Basic logging setup
├── cache/                  # Directory for cached responses
│   ├── api_responses/      # Raw API response cache
│   ├── processed_data/     # Processed entity cache
│   └── checkpoints/        # Processing checkpoints
├── output/                 # Directory for final output
└── templates/              # Prompt templates for LLM
```

## 3. Setup and Configuration
- Use `uv` for dependency management
- Required libraries:
  - `requests` or `httpx`: For API calls
  - `pandas`: For data manipulation
  - `pydantic`: For schema validation
  - `tqdm`: For progress bars
  - `python-dotenv`: For environment variables
  - `openpyxl`: For Excel export
  - `slugify`: For slug generation
  - `logging`: For basic logging

## 4. Input Processing
- Read CSV file containing two columns: "City" and "Cafes Needed"
- Import city ID mapping JSON file for Contentful references
- Validate input format
- Create processing queue prioritized by number of cafes needed

## 5. Data Collection Phase
- For each city, query LLM to find the best cafes (number specified in CSV)
  - Focus on 3rd wave, modern, and unique coffee shops
- Parse structured data from LLM responses
- Validate initial data against schemas
- Cache raw responses to minimize API usage
- Store results in working DataFrame and persistent cache

## 6. Enhanced Slug Generation
- Create unique slug for each cafe using format: `{cafe-name}-{street-name}-{city}`
- Remove special characters, lowercase, and replace spaces with hyphens
- Handle edge cases:
  - Multiple locations: Add neighborhood or area identifier
  - Same street name: Add street number or nearest landmark
  - No street name: Use neighborhood or district instead
  - Duplicate slugs: Add numeric suffix (e.g., `-2`, `-3`)
- Implement validation to ensure uniqueness across all generated slugs

## 7. Data Enrichment Phase
For each cafe, generate and store data according to Contentful schema:
- Basic info:
  - Cafe Name
  - Cafe Address
  - Slug (generated using enhanced format)
  - Publish Date (current date)
  - Author Name: "Chris Jordan"
  - Excerpt (short summary)
- Ratings (all on scale 0-10, except Vibe which is 1-10):
  - Overall Score
  - Coffee Score
  - Food Score
  - Vibe Score (integer)
  - Atmosphere Score
  - Service Score
  - Value Score
- Rich text sections (each 3-5 sentences, creative and non-repetitive):
  - Vibe Description: Fun, descriptive flowing paragraph about the atmosphere
  - The Story: Details on cafe origins, inspiration, and what they're known for
  - Craft & Expertise: Quality of coffee, barista skills, customer experience
  - What Sets Them Apart: Unique aspects that make the cafe worth visiting
- Location data:
  - Cafe Lat Lon (obtained via LLM)
  - City Reference (link to city content type using provided city IDs)

## 8. Pydantic Schema (Updated for Contentful)
```python
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
```

## 9. Caching Strategy
Three-tier approach to minimize API calls:
- **Request-Level Cache**: Avoid duplicate API calls
- **Entity-Level Cache**: Store processed cafe data
- **Batch Processing Cache**: Enable resume capability

## 10. Error Handling
Robust handling of API issues:
- Exponential backoff with jitter
- Request queuing for rate limit management
- Comprehensive exception handling
- Basic logging of failures and retries
- Checkpointing for failure recovery

## 11. Text Generation Optimization
- Create specialized text generation prompts for each section:
  - **Vibe Description**: Fun, descriptive, creative atmosphere description
  - **The Story**: Cafe origins, inspiration, and notable history
  - **Craft & Expertise**: Coffee quality, barista skills, customer experience
  - **What Sets Them Apart**: Unique differentiating factors
- Implement diversity checks to ensure non-repetitive content across sections
- Develop style guide parameters for LLM to maintain consistent tone
- Create test mode to experiment with prompt variations before full run

## 12. Excel Export for Data Auditing
- Export all collected data to Excel for manual review
- Include import function to read edited Excel back into system
- Implement validation on Excel import to maintain data integrity

## 13. Contentful Export
- Format data according to Contentful's JSON structure
- Ensure all fields match expected types and validations
- Create proper rich text format for text fields
- Format location data as required by Contentful
- Create proper reference links to city content type using provided city IDs
- Support schema verification before export

## 14. Implementation Steps
1. Set up project structure and environment
2. Implement data input processing for CSV and city ID mapping JSON
3. Develop LLM client with caching and error handling
4. Build schema validation aligned with Contentful
5. Create data collection module for finding best 3rd wave cafes
6. Develop enhanced slug generation system
7. Implement specialized text generation templates
8. Build storage and checkpointing system
9. Create Excel export/import functionality
10. Develop Contentful-compatible JSON export
11. Test with small sample set and refine prompts
12. Add configuration options and documentation
13. Run full collection with approved settings
