"""
File ID Cache Module

Manages caching of Telegram file_ids to avoid re-uploading the same files.
"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict
import threading


class FileIdCache:
    """Manages file_id cache for Telegram files."""
    
    def __init__(self, cache_file: str = "file_id_cache.json"):
        """
        Initialize FileIdCache.
        
        Args:
            cache_file: Path to JSON file for persisting cache
        """
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, str] = {}  # file_key -> file_id
        self.lock = threading.Lock()  # Thread-safe access
        
        # Load existing cache
        self._load_cache()
    
    def _get_file_key(self, file_path: str) -> str:
        """
        Generate a cache key for a file.
        
        Uses file hash for better reliability (handles file moves/renames).
        
        Args:
            file_path: Path to the file (local or Yandex Disk path)
        
        Returns:
            Cache key string
        """
        file_path_obj = Path(file_path)
        
        # If file exists locally, use hash
        if file_path_obj.exists() and file_path_obj.is_file():
            try:
                # Calculate MD5 hash of file
                hash_md5 = hashlib.md5()
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_md5.update(chunk)
                return f"hash:{hash_md5.hexdigest()}"
            except Exception as e:
                # If hash calculation fails, fall back to path
                print(f"Warning: Could not calculate hash for {file_path}: {e}")
                return f"path:{file_path}"
        else:
            # For Yandex Disk paths or non-existent files, use path
            return f"path:{file_path}"
    
    def _load_cache(self) -> None:
        """Load cache from JSON file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded {len(self.cache)} file_ids from cache")
            except Exception as e:
                print(f"Error loading cache file: {e}")
                self.cache = {}
        else:
            self.cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving cache file: {e}")
    
    def get_file_id(self, file_path: str) -> Optional[str]:
        """
        Get cached file_id for a file.
        
        Args:
            file_path: Path to the file
        
        Returns:
            file_id if found in cache, None otherwise
        """
        with self.lock:
            file_key = self._get_file_key(file_path)
            return self.cache.get(file_key)
    
    def set_file_id(self, file_path: str, file_id: str) -> None:
        """
        Store file_id in cache.
        
        Args:
            file_path: Path to the file
            file_id: Telegram file_id
        """
        with self.lock:
            file_key = self._get_file_key(file_path)
            self.cache[file_key] = file_id
            self._save_cache()
    
    def remove_file_id(self, file_path: str) -> None:
        """
        Remove file_id from cache.
        
        Args:
            file_path: Path to the file
        """
        with self.lock:
            file_key = self._get_file_key(file_path)
            if file_key in self.cache:
                del self.cache[file_key]
                self._save_cache()
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        with self.lock:
            self.cache.clear()
            self._save_cache()
    
    def get_cache_size(self) -> int:
        """
        Get number of cached entries.
        
        Returns:
            Number of cached file_ids
        """
        with self.lock:
            return len(self.cache)

