import json
import os
import time
from typing import Any, Optional
from pathlib import Path


class CacheManager:
    def __init__(self, cache_dir: str):
        """Initialize cache manager with specified directory."""
        self.cache_dir = Path(cache_dir)
        self._ensure_cache_dirs()
    
    def _ensure_cache_dirs(self):
        """Ensure all cache directories exist."""
        for subdir in ['api_responses', 'processed_data', 'checkpoints']:
            (self.cache_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, cache_type: str, key: str) -> Path:
        """Get the full path for a cache file."""
        return self.cache_dir / cache_type / f"{key}.json"
    
    def save(self, cache_type: str, key: str, data: Any, ttl: Optional[int] = None):
        """Save data to cache with optional TTL (in seconds)."""
        cache_data = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
        
        cache_path = self._get_cache_path(cache_type, key)
        with cache_path.open('w') as f:
            json.dump(cache_data, f, indent=2)
    
    def load(self, cache_type: str, key: str) -> Optional[Any]:
        """Load data from cache if it exists and is not expired."""
        cache_path = self._get_cache_path(cache_type, key)
        
        if not cache_path.exists():
            return None
            
        try:
            with cache_path.open('r') as f:
                cache_data = json.load(f)
            
            # Check TTL if it exists
            if cache_data.get('ttl'):
                if time.time() - cache_data['timestamp'] > cache_data['ttl']:
                    return None
                    
            return cache_data['data']
        except (json.JSONDecodeError, KeyError):
            return None
    
    def invalidate(self, cache_type: str, key: str):
        """Remove a specific cache entry."""
        cache_path = self._get_cache_path(cache_type, key)
        if cache_path.exists():
            cache_path.unlink()
    
    def clear_all(self, cache_type: Optional[str] = None):
        """Clear all cache entries of a specific type or all types if none specified."""
        if cache_type:
            cache_dir = self.cache_dir / cache_type
            if cache_dir.exists():
                for cache_file in cache_dir.glob('*.json'):
                    cache_file.unlink()
        else:
            for subdir in ['api_responses', 'processed_data', 'checkpoints']:
                cache_dir = self.cache_dir / subdir
                if cache_dir.exists():
                    for cache_file in cache_dir.glob('*.json'):
                        cache_file.unlink() 