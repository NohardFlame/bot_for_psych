"""
Yandex Disk Handler Module

This module provides functionality to list, download, and publish files on Yandex Disk.
"""

import io
import time
import yadisk
import yadisk.exceptions as yadisk_exceptions
from typing import List, Optional, Dict, Any
from pathlib import Path

from yadisk.types import AvailableUntilVerbose, PublicSettings, PublicSettingsAccess


# Custom Exceptions
class YandexDiskAPIError(Exception):
    """Base exception for Yandex Disk API errors."""
    pass


class FileNotFoundError(YandexDiskAPIError):
    """Raised when a file doesn't exist on Yandex Disk."""
    pass


class APIError(YandexDiskAPIError):
    """Raised for HTTP errors from the Yandex Disk API."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class YandexDiskHandler:
    """
    Handler for listing, downloading, and publishing files on Yandex Disk.
    
    This class provides methods to:
    - List files and folders in directories (similar to 'ls' command)
    - Download and read text file contents
    - Download files to local storage
    - Publish files as temporary public links
    """
    
    BASE_API_URL = "https://cloud-api.yandex.net/v1/disk"
    
    def __init__(self, token_file: str = "ya_api_token.txt", token: Optional[str] = None):
        """
        Initialize the YandexDiskHandler.
        
        Args:
            token_file: Path to the file containing the Yandex API token.
                       Defaults to "ya_api_token.txt" in the current directory.
                       Ignored if token parameter is provided.
            token: Optional token string. If provided, uses this token directly
                   instead of reading from file.
        
        Raises:
            FileNotFoundError: If the token file doesn't exist and token is not provided.
            APIError: If the token file is empty or invalid, or token is empty.
        """
        if token is not None:
            self.token = token.strip()
        else:
            token_path = Path(token_file)
            if not token_path.exists():
                raise FileNotFoundError(f"Token file not found: {token_file}")
            
            with open(token_path, 'r', encoding='utf-8') as f:
                self.token = f.read().strip()
        
        if not self.token:
            raise APIError("API token is empty")
        
        # Initialize yadisk client
        self.client = yadisk.Client(token=self.token)
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path format for SDK compatibility and prepend "bot/" folder.
        
        SDK expects paths in format "disk:/path" or "disk:/" for root.
        This method converts paths from "/path" or "path" format to "disk:/path"
        and automatically prepends "bot/" so all operations work from the "bot" folder
        instead of the root.
        
        Args:
            path: Path to normalize.
        
        Returns:
            Normalized path string with "bot/" prefix (e.g., "disk:/bot/path").
        """
        # Handle empty string as root
        if not path or path == "/":
            return "disk:/bot"
        
        # First, normalize to "disk:/" format
        if not path.startswith("disk:/"):
            if path.startswith("/"):
                normalized = "disk:" + path
            else:
                normalized = "disk:/" + path
        else:
            normalized = path
        
        # Handle root case
        if normalized == "disk:/":
            return "disk:/bot"
        
        # Check if path already starts with "disk:/bot/" or is exactly "disk:/bot" to avoid double-prefixing
        if normalized.startswith("disk:/bot/") or normalized == "disk:/bot":
            return normalized
        
        # Insert "bot/" after "disk:/"
        # "disk:/path" -> "disk:/bot/path"
        if normalized.startswith("disk:/"):
            return "disk:/bot/" + normalized[6:]  # Remove "disk:/" (6 chars), add "disk:/bot/"
        
        # Fallback (shouldn't reach here, but just in case)
        return normalized
    
    def _handle_sdk_exception(self, exception: Exception) -> None:
        """
        Map SDK exceptions to our custom exceptions.
        
        Args:
            exception: Exception raised by yadisk SDK.
        
        Raises:
            FileNotFoundError: For path not found errors.
            APIError: For other API errors.
        """
        if isinstance(exception, yadisk_exceptions.PathNotFoundError):
            raise FileNotFoundError(f"Resource not found: {str(exception)}") from exception
        elif isinstance(exception, (yadisk_exceptions.YaDiskError, yadisk_exceptions.BadRequestError, 
                                   yadisk_exceptions.UnauthorizedError, yadisk_exceptions.ForbiddenError,
                                   yadisk_exceptions.NotFoundError, yadisk_exceptions.ConflictError, 
                                   yadisk_exceptions.PayloadTooLargeError, yadisk_exceptions.UnsupportedMediaTypeError, 
                                   yadisk_exceptions.UnprocessableEntityError, yadisk_exceptions.TooManyRequestsError, 
                                   yadisk_exceptions.InternalServerErrorError, yadisk_exceptions.NotImplementedError, 
                                   yadisk_exceptions.BadGatewayError, yadisk_exceptions.ServiceUnavailableError, 
                                   yadisk_exceptions.GatewayTimeoutError, yadisk_exceptions.RequestError)):
            # Extract status code if available
            status_code = getattr(exception, 'status_code', None)
            error_msg = str(exception)
            raise APIError(error_msg, status_code=status_code) from exception
        else:
            # For any other exception, wrap it as APIError
            raise APIError(f"Unexpected error: {str(exception)}") from exception
    
    def _resource_to_dict(self, resource) -> Dict[str, Any]:
        """
        Convert yadisk ResourceObject to dictionary format for backward compatibility.
        
        Args:
            resource: yadisk ResourceObject or dict.
        
        Returns:
            Dictionary representation of the resource.
        """
        if isinstance(resource, dict):
            return resource
        
        # If it's a ResourceObject, convert to dict
        result = {}
        for key in ['name', 'type', 'path', 'size', 'modified', 'created', 'mime_type', 
                   'md5', 'public_url', 'public_key', 'preview', 'file', 'href']:
            if hasattr(resource, key):
                value = getattr(resource, key)
                if value is not None:
                    result[key] = value
        
        return result
    
    def publish_temporary_link(self, file_path: str, expiration_seconds: int = 30) -> dict:
        """
        Publish a file or folder as a temporary public link that expires after specified seconds.
        
        This method creates a public link accessible to anyone for a limited time.
        The link will automatically expire after the specified duration.
        
        Args:
            file_path: Path to the file or folder on Yandex Disk (e.g., "/path/to/file.pdf").
            expiration_seconds: Number of seconds until the link expires. Defaults to 30.
        
        Returns:
            Dictionary containing 'public_url' key with the public link.
        
        Raises:
            APIError: For API errors.
            FileNotFoundError: If the file doesn't exist.
        """
        # Normalize path format
        normalized_path = self._normalize_path(file_path)
        
        # Calculate expiration timestamp
        expiration_timestamp = int(time.time()) + expiration_seconds

        # res = self.client.get_public_settings(normalized_path, allow_address_access=True)
        # print(res)
        # return {}
        
        try:
            # Construct PublicSettings dict with expiration
            public_settings = PublicSettings(
                available_until = expiration_timestamp,
                available_until_verbose=AvailableUntilVerbose(
                    enabled = True,
                    timestamp = expiration_timestamp
                ),
                permisions = ["read_without_download"],
                allow_address_access = True,
                read_only = True,
                accesses = [
                    PublicSettingsAccess(
                        macros = ["all"],
                        rights = ["read_without_download"]
                    )
                ]
            )
            
            # Publish without email restrictions (public link)
            link_object = self.client.publish(
                normalized_path,
                public_settings=public_settings
            )
            print(public_settings)
            print(link_object)
            
            # Get public URL from the link object
            result = {}
            if link_object:
                # Link object has href attribute
                public_url = getattr(link_object, 'href', None)
                if public_url:
                    result['public_url'] = public_url
                # Also try to get from meta
                if not public_url:
                    for attempt in range(3):
                        public_url = self._get_public_url(file_path)
                        if public_url:
                            result['public_url'] = public_url
                            break
                        if attempt < 2:
                            time.sleep(0.5)
            
            return result
        except Exception as e:
            self._handle_sdk_exception(e)
            
    
    def _get_public_url(self, file_path: str) -> Optional[str]:
        """
        Get the public URL for a published resource.
        
        Args:
            file_path: Path to the file or folder on Yandex Disk.
        
        Returns:
            Public URL string if available, None otherwise.
        """
        try:
            # Normalize path format
            normalized_path = self._normalize_path(file_path)
            
            # Get metadata with public_url field
            # Try with fields parameter first
            try:
                meta = self.client.get_meta(normalized_path, fields=["public_url"])
            except Exception:
                # If fields parameter fails, try without it
                meta = self.client.get_meta(normalized_path)
            
            if meta:
                # Try to get public_url from meta object
                public_url = getattr(meta, 'public_url', None)
                if public_url:
                    return public_url
                
                # If not found as attribute, try converting to dict
                if hasattr(meta, '__dict__'):
                    meta_dict = self._resource_to_dict(meta)
                    return meta_dict.get('public_url')
            
            return None
        except (APIError, FileNotFoundError):
            # If we can't get the public URL, return None
            return None
        except Exception as e:
            # Handle SDK exceptions silently for this method
            if isinstance(e, (yadisk_exceptions.PathNotFoundError, yadisk_exceptions.NotFoundError)):
                return None
            # For other exceptions, also return None silently
            return None
    
    def list_directory(self, path: str = "/", limit: Optional[int] = None, offset: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List files and folders in a directory (similar to 'ls' command).
        
        Args:
            path: Path to the directory on Yandex Disk. Defaults to "/" (root).
            limit: Optional limit on the number of items to return.
            offset: Optional offset for pagination.
        
        Returns:
            List of dictionaries containing item information. Each dictionary includes:
            - name: Item name
            - type: Item type ("file" or "dir")
            - path: Full path to the item
            - size: File size in bytes (only for files)
            - modified: Modification date/time
            - created: Creation date/time (if available)
            - mime_type: MIME type (for files)
            - md5: MD5 hash (for files)
            - public_url: Public URL (if published)
            - public_key: Public key (if published)
        
        Raises:
            APIError: For API errors.
            FileNotFoundError: If the directory doesn't exist.
        """
        try:
            # Normalize path format
            normalized_path = self._normalize_path(path)
            
            # Use SDK's listdir method
            items = list(self.client.listdir(normalized_path, limit=limit, offset=offset))
            
            # Convert ResourceObject items to dictionaries
            return [self._resource_to_dict(item) for item in items]
        except Exception as e:
            self._handle_sdk_exception(e)
    
    def _get_download_url(self, file_path: str) -> str:
        """
        Get the download URL for a file on Yandex Disk.
        
        Args:
            file_path: Path to the file on Yandex Disk.
        
        Returns:
            Download URL string.
        
        Raises:
            APIError: For API errors.
            FileNotFoundError: If the file doesn't exist.
        """
        try:
            # Normalize path format
            if not file_path.startswith("disk:/") and file_path != "/":
                if file_path.startswith("/"):
                    file_path = "disk:" + file_path
                else:
                    file_path = "disk:/" + file_path
            
            # Use SDK's get_download_link method
            download_url = self.client.get_download_link(file_path)
            if not download_url:
                raise APIError("Download URL not found in API response")
            return download_url
        except Exception as e:
            self._handle_sdk_exception(e)
    
    def _is_image_file(self, file_path: str) -> bool:
        """
        Check if a file is an image based on its extension.
        
        Args:
            file_path: Path to the file.
        
        Returns:
            True if the file is an image, False otherwise.
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in image_extensions
    
    def _cloud_path_to_local_path(self, cloud_path: str, download_folder: str = "downloads") -> str:
        """
        Convert cloud path to local download path, preserving folder structure.
        
        Converts paths like "disk:/program_1/1_day/file.jpg" to 
        "downloads/program_1/1_day/file.jpg", preserving the folder hierarchy.
        
        Args:
            cloud_path: Path on Yandex Disk (e.g., "disk:/program_1/1_day/file.jpg")
            download_folder: Base folder for downloads. Defaults to "downloads".
        
        Returns:
            Local file path with folder structure preserved.
        """
        # Normalize the cloud path
        normalized = self._normalize_path(cloud_path)
        
        # Remove "disk:" prefix
        if normalized.startswith("disk:"):
            relative_path = normalized[5:]  # Remove "disk:" (5 characters)
        else:
            relative_path = normalized
        
        # Remove leading slash if present
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]
        
        # If path is empty after stripping, it's a root file
        if not relative_path:
            # This shouldn't happen for files, but handle it
            filename = Path(cloud_path).name
            return str(Path(download_folder) / filename)
        
        # Build local path preserving structure
        local_path = Path(download_folder) / relative_path
        
        return str(local_path)
    
    def get_text_file_content(self, file_path: str, encoding: str = 'utf-8') -> str:
        """
        Download and return the content of a text file as a string.
        
        Args:
            file_path: Path to the .txt file on Yandex Disk.
            encoding: Text encoding to use when reading the file. Defaults to 'utf-8'.
        
        Returns:
            File content as a string.
        
        Raises:
            APIError: For API errors.
            FileNotFoundError: If the file doesn't exist.
            UnicodeDecodeError: If the file cannot be decoded with the specified encoding.
        """
        try:
            # Normalize path format
            normalized_path = self._normalize_path(file_path)
            
            # Download to memory buffer
            buffer = io.BytesIO()
            self.client.download(normalized_path, buffer)
            buffer.seek(0)
            
            # Decode content
            content = buffer.read().decode(encoding)
            return content
        except UnicodeDecodeError as e:
            raise APIError(f"Failed to decode file with encoding '{encoding}': {str(e)}") from e
        except Exception as e:
            self._handle_sdk_exception(e)
    
    def download_file(
        self,
        file_path: str,
        download_folder: str = "downloads"
    ) -> str:
        """
        Download a file from Yandex Disk and save it to local storage.
        
        This method preserves the folder structure from cloud storage to prevent
        filename conflicts. It checks if the file already exists before downloading
        to avoid unnecessary downloads (especially important for large files like videos).
        
        This method is synchronous and blocks until the entire file has been
        downloaded and saved to disk. When it returns, the file is ready to use.
        
        Args:
            file_path: Path to the file on Yandex Disk (e.g., "disk:/program_1/1_day/file.jpg").
            download_folder: Base folder for downloads. Defaults to "downloads".
        
        Returns:
            Path to the downloaded file. The file is fully downloaded and ready to use.
            If the file already exists locally, returns the existing path without re-downloading.
        
        Raises:
            APIError: For API errors.
            FileNotFoundError: If the file doesn't exist on Yandex Disk.
        """
        # Convert cloud path to local path with folder structure
        local_file_path = self._cloud_path_to_local_path(file_path, download_folder)
        local_path_obj = Path(local_file_path)
        
        # Check if file already exists
        if local_path_obj.exists():
            # File already downloaded, return existing path
            return str(local_file_path)
        
        # Create parent directories if they don't exist
        local_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Normalize path format for SDK
            normalized_path = self._normalize_path(file_path)
            
            # Use SDK to download directly to file
            self.client.download(normalized_path, str(local_file_path))
            
            return str(local_file_path)
        except IOError as e:
            raise APIError(f"Failed to save file to {local_file_path}: {str(e)}") from e
        except Exception as e:
            self._handle_sdk_exception(e)

