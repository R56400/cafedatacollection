"""
Cafe Data Collection

A Python system to collect, process, and store coffee shop data using LLMs,
with built-in caching, error handling, and schema validation.
"""

__version__ = "0.1.0"

from .data_collection import DataCollector
from .llm_client import LLMClient
from .geocoding import GeocodingClient
from .contentful_export import ContentfulExporter
from .excel_export import ExcelExporter
from .schemas import CafeReview, Location, Rating, RichText, RichTextContent

__all__ = [
    "DataCollector",
    "LLMClient",
    "GeocodingClient",
    "ContentfulExporter",
    "ExcelExporter",
    "CafeReview",
    "Location",
    "Rating",
    "RichText",
    "RichTextContent"
] 