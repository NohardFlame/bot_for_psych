"""
Content Fetcher Module

Retrieves content from Yandex Disk folders
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from disk_api_handler.disk_handler import YandexDiskHandler, FileNotFoundError, APIError
from datetime import date


class ContentFetcher:
    """Fetches content from Yandex Disk day folders."""
    
    def __init__(self, disk_handler: YandexDiskHandler):
        """
        Initialize ContentFetcher.
        
        Args:
            disk_handler: YandexDiskHandler instance
        """
        self.disk_handler = disk_handler
    
    def _is_image_file(self, file_path: str) -> bool:
        """
        Check if a file is an image based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is an image, False otherwise
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in image_extensions
    
    def _is_text_file(self, file_path: str) -> bool:
        """
        Check if a file is a text file based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is a text file, False otherwise
        """
        text_extensions = {'.txt', '.text'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in text_extensions
    
    def _is_media_file(self, file_path: str) -> bool:
        """
        Check if a file is a media file (image, video, or audio) based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is a media file, False otherwise
        """
        # Image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
        # Video extensions
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ogv'}
        # Audio extensions
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus', '.amr'}
        
        file_ext = Path(file_path).suffix.lower()
        return file_ext in (image_extensions | video_extensions | audio_extensions)
    
    def _is_document_file(self, file_path: str) -> bool:
        """
        Check if a file is a document file (.doc, .docx, .pdf) based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is a document file, False otherwise
        """
        document_extensions = {'.doc', '.docx', '.pdf'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in document_extensions
    
    def fetch_day_content(self, folder_path: str) -> Dict[str, Any]:
        """
        Fetch all content from a day folder.
        
        Args:
            folder_path: Path to the day folder on Yandex Disk (e.g., "disk:/program_1/1_day")
        
        Returns:
            Dictionary with keys:
            - text_content: str or None (content of .txt file)
            - media_files: List[str] (local paths to media files: images, videos, audio)
            - document_files: List[str] (local paths to document files: .doc, .docx, .pdf)
            - error: str or None (error message if any)
        """
        result = {
            'text_content': None,
            'media_files': [],
            'document_files': [],
            'error': None
        }
        
        try:
            # List all files in the folder
            items = self.disk_handler.list_directory(folder_path)
            
            if not items:
                result['error'] = "Folder is empty"
                return result
            
            # Separate files by type
            text_files = []
            media_files = []
            document_files = []
            
            for item in items:
                if item.get('type') != 'file':
                    continue
                
                file_path = item.get('path', '')
                
                if self._is_text_file(file_path):
                    text_files.append(file_path)
                elif self._is_media_file(file_path):
                    media_files.append(file_path)
                elif self._is_document_file(file_path):
                    document_files.append(file_path)
                # Ignore other file types
            
            # Fetch text content (use first .txt file found)
            if text_files:
                try:
                    result['text_content'] = self.disk_handler.get_text_file_content(text_files[0])
                except (APIError, FileNotFoundError) as e:
                    result['error'] = f"Failed to read text file: {str(e)}"
            
            # Download media files (images, videos, audio)
            for media_path in media_files:
                try:
                    local_path = self.disk_handler.download_file(media_path)
                    result['media_files'].append(local_path)
                except (APIError, FileNotFoundError) as e:
                    # Log error but continue with other files
                    error_msg = f"Some media files failed to download: {str(e)}"
                    if not result['error']:
                        result['error'] = error_msg
                    else:
                        result['error'] += f"; {error_msg}"
            
            # Download document files (.doc, .docx, .pdf)
            for doc_path in document_files:
                try:
                    local_path = self.disk_handler.download_file(doc_path)
                    result['document_files'].append(local_path)
                except (APIError, FileNotFoundError) as e:
                    # Log error but continue with other files
                    error_msg = f"Some document files failed to download: {str(e)}"
                    if not result['error']:
                        result['error'] = error_msg
                    else:
                        result['error'] += f"; {error_msg}"
            
        except FileNotFoundError:
            result['error'] = "Day folder not found"
        except APIError as e:
            result['error'] = f"API error: {str(e)}"
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
        
        return result
    
    def get_available_days(self, program_key: str, max_day: int) -> List[int]:
        """
        Check Yandex Disk for existing day folders.
        Returns list of day numbers that have corresponding folders.
        
        Args:
            program_key: Program key (e.g., "program_1")
            max_day: Maximum day number to check (based on begin_date and current date)
        
        Returns:
            List of day numbers that have corresponding folders (e.g., [1, 2, 3, 5, 7])
        """
        available = []
        for day_num in range(1, max_day + 1):
            day_folder = f"{day_num}_day"
            folder_path = f"disk:/{program_key}/{day_folder}"
            
            try:
                # Try to list directory - if it exists, this will succeed
                items = self.disk_handler.list_directory(folder_path)
                # If we can list it, it exists
                available.append(day_num)
            except FileNotFoundError:
                # Folder doesn't exist, skip it
                continue
            except Exception:
                # Other errors (API errors, etc.), skip it
                continue
        
        return available

