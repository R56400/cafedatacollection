# Cafe Data Collection

A Python system to collect, process, and store coffee shop data using Large Language Models (LLMs), with built-in caching, error handling, and schema validation conforming to the Contentful schema.

## Features

- Automated collection of cafe data using LLMs
- Geocoding support via Google Maps API
- Rich text content generation for cafe descriptions
- Caching system to minimize API usage
- Progress tracking and resume capability
- Export to Contentful format
- Rate limiting and error handling
- Configurable logging

## Prerequisites

- Python 3.8+
- OpenAI API key
- Google Maps API key
- Contentful space ID and access token

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/cafe-data-collection.git
   cd cafe-data-collection
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the environment template and fill in your API keys:
   ```bash
   cp .env.template .env
   ```
   Edit `.env` with your API keys and configuration.

## Input Files

### City Data CSV
Create a CSV file with the following columns:
- `City`: Name of the city
- `Cafes Needed`: Number of cafes to collect for that city

Example (`input.csv`):
```csv
City,Cafes Needed
San Francisco,10
New York,15
Los Angeles,12
```

### City Mapping JSON
Create a JSON file mapping cities to their Contentful IDs:

Example (`city_mappings.json`):
```json
{
    "San Francisco": "sf123",
    "New York": "nyc456",
    "Los Angeles": "la789"
}
```

## Usage

Basic usage:
```bash
python -m cafe_data_collection input.csv city_mappings.json
```

With optional arguments:
```bash
python -m cafe_data_collection input.csv city_mappings.json \
    --contentful-output export.json
```

Available options:
- `--no-contentful`: Skip Contentful export
- `--contentful-output PATH`: Specify Contentful export path

## Output

The script generates Contentful JSON output:

- Contentful JSON (default: `output/contentful_export_TIMESTAMP.json`)
  - Formatted for Contentful import
  - Includes all required fields and references
  - Rich text formatting

## Caching

The system implements three levels of caching:
- API responses (24 hours)
- Processed data (1 week)
- Geocoding results (30 days)

Cache files are stored in the `cache/` directory.

## Development

### Project Structure
```
cafe_data_collection/
├── __init__.py           # Package initialization
├── main.py              # Entry point
├── config.py            # Configuration settings
├── llm_client.py        # LLM API interaction
├── data_collection.py   # Core collection logic
├── geocoding.py         # Google Maps integration
├── contentful_export.py # Contentful export
├── schemas.py           # Data models
└── utils/
    ├── caching.py       # Caching system
    └── logging.py       # Logging setup
```

### Adding New Features

1. Update schemas in `schemas.py`
2. Modify collection logic in `data_collection.py`
3. Update export formats as needed
4. Add new configuration in `config.py`

## Error Handling

The system implements comprehensive error handling:
- API rate limiting
- Request retries with exponential backoff
- Progress saving
- Detailed logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details
