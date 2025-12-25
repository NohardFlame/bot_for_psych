"""
Present Navigator Module

Handles reading and navigating the present folder structure on Yandex Disk.
"""

from typing import List, Optional
from disk_api_handler.disk_handler import YandexDiskHandler, APIError, FileNotFoundError


class PresentNavigator:
    """Handles navigation through the present folder structure on Yandex Disk."""
    
    BASE_PATH = "/present"
    
    @staticmethod
    def validate_folder_path(path: str) -> bool:
        """
        Ensure path is within /present directory for security.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid and within /present directory, False otherwise
        """
        if not path:
            return True  # Empty path means root of present folder
        
        # Normalize path
        normalized = path.strip().strip('/')
        
        # Check if path tries to escape the present directory
        if normalized.startswith('..') or '/../' in normalized:
            return False
        
        # Path should be relative to present folder
        return True
    
    @staticmethod
    def _get_full_path(relative_path: str = "") -> str:
        """
        Get full path to folder within present directory.
        
        Args:
            relative_path: Relative path within present folder (empty for root)
            
        Returns:
            Full path string (e.g., "/present" or "/present/option1")
        """
        if not relative_path or relative_path == "/":
            return PresentNavigator.BASE_PATH
        
        # Remove leading/trailing slashes
        relative_path = relative_path.strip().strip('/')
        
        # Combine base path with relative path
        return f"{PresentNavigator.BASE_PATH}/{relative_path}"
    
    @staticmethod
    def get_folder_message(disk_handler: YandexDiskHandler, folder_path: str = "") -> str:
        """
        Read msg.txt from folder, return empty string if not found.
        
        Args:
            disk_handler: YandexDiskHandler instance
            folder_path: Relative path within present folder (empty for root)
            
        Returns:
            Content of msg.txt file, or empty string if file doesn't exist
        """
        try:
            full_path = PresentNavigator._get_full_path(folder_path)
            msg_file_path = f"{full_path}/msg.txt"
            
            print(f"DEBUG: Attempting to read msg.txt from: {msg_file_path}")
            content = disk_handler.get_text_file_content(msg_file_path)
            print(f"DEBUG: Successfully read msg.txt, content length: {len(content) if content else 0}")
            return content.strip() if content else ""
        except FileNotFoundError as e:
            # msg.txt doesn't exist, return empty string
            print(f"DEBUG: msg.txt not found at {PresentNavigator._get_full_path(folder_path)}/msg.txt: {e}")
            return ""
        except APIError as e:
            # API error, log and return empty string
            print(f"DEBUG: API error reading msg.txt from {PresentNavigator._get_full_path(folder_path)}/msg.txt: {e}")
            return ""
        except Exception as e:
            # Any other error, log and return empty string
            print(f"DEBUG: Unexpected error reading msg.txt from {PresentNavigator._get_full_path(folder_path)}/msg.txt: {type(e).__name__}: {e}")
            return ""
    
    @staticmethod
    def get_subfolders(disk_handler: YandexDiskHandler, folder_path: str = "") -> List[str]:
        """
        List all subfolders in a directory.
        
        Args:
            disk_handler: YandexDiskHandler instance
            folder_path: Relative path within present folder (empty for root)
            
        Returns:
            List of subfolder names (not full paths)
        """
        try:
            full_path = PresentNavigator._get_full_path(folder_path)
            
            items = disk_handler.list_directory(full_path)
            
            # Filter to only include directories
            subfolders = []
            for item in items:
                item_type = item.get('type', '')
                if item_type == 'dir':
                    folder_name = item.get('name', '')
                    if folder_name:  # Skip empty names
                        subfolders.append(folder_name)
            
            # Sort alphabetically for consistent display
            subfolders.sort()
            
            return subfolders
        except (FileNotFoundError, APIError):
            # Folder doesn't exist or API error, return empty list
            return []
        except Exception:
            # Any other error, return empty list
            return []
    
    @staticmethod
    def get_parent_path(current_path: str) -> Optional[str]:
        """
        Get parent path of current path.
        
        Args:
            current_path: Current relative path (e.g., "option1/option2")
            
        Returns:
            Parent path (e.g., "option1") or None if at root
        """
        if not current_path or current_path == "/":
            return None
        
        # Remove leading/trailing slashes
        path = current_path.strip().strip('/')
        
        # Split by slash and get parent
        parts = path.split('/')
        if len(parts) <= 1:
            return None
        
        # Return parent path
        return '/'.join(parts[:-1])

