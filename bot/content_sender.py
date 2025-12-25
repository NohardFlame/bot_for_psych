"""
Content Sender Module

Sends messages, images, and file links via Telegram
"""

import telebot
import telebot.apihelper
from typing import List, Dict, Any, Optional
from pathlib import Path
from disk_api_handler.disk_handler import YandexDiskHandler, APIError
import telebot.types as types

# Handle both package and direct execution
try:
    from .file_id_cache import FileIdCache
except ImportError:
    from file_id_cache import FileIdCache


class ContentSender:
    """Sends content to users via Telegram."""
    
    def __init__(
        self,
        bot: telebot.TeleBot,
        disk_handler: YandexDiskHandler,
        file_id_cache: Optional[FileIdCache] = None,
        cache_chat_id: Optional[int] = None
    ):
        """
        Initialize ContentSender.
        
        Args:
            bot: TeleBot instance
            disk_handler: YandexDiskHandler instance
            file_id_cache: Optional FileIdCache instance for caching file_ids
            cache_chat_id: Optional chat ID where files are uploaded for caching.
                         If None, caching is disabled.
        """
        self.bot = bot
        self.disk_handler = disk_handler
        self.file_id_cache = file_id_cache
        self.cache_chat_id = cache_chat_id
    
    def send_text_content(self, chat_id: int, text: str, reply_markup=None, parse_mode: str = "HTML") -> bool:
        """
        Send text content to user.
        
        Args:
            chat_id: Telegram chat ID
            text: Text content to send (supports HTML formatting)
            reply_markup: Optional inline keyboard markup
            parse_mode: Parse mode for formatting ("HTML", "MarkdownV2", or None)
                       Defaults to "HTML" to support formatting in text files
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except Exception as e:
            print(f"Error sending text: {str(e)}")
            return False
    
    def send_images(self, chat_id: int, image_paths: List[str]) -> bool:
        """
        Send images to user.
        
        Args:
            chat_id: Telegram chat ID
            image_paths: List of local file paths to images
        
        Returns:
            True if all images sent successfully, False otherwise
        """
        success = True
        for image_path in image_paths:
            if not self._send_media_with_cache(chat_id, image_path, 'photo', protect_content=True):
                success = False
        
        return success
    
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
    
    def _is_video_file(self, file_path: str) -> bool:
        """
        Check if a file is a video based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is a video, False otherwise
        """
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.m4v', '.3gp', '.ogv'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in video_extensions
    
    def _is_audio_file(self, file_path: str) -> bool:
        """
        Check if a file is an audio file based on its extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            True if the file is an audio file, False otherwise
        """
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.opus', '.amr'}
        file_ext = Path(file_path).suffix.lower()
        return file_ext in audio_extensions
    
    def _get_or_upload_file_id(
        self,
        file_path: str,
        file_type: str  # 'photo', 'video', 'audio', 'document'
    ) -> Optional[str]:
        """
        Get file_id from cache or upload file to cache chat and store file_id.
        
        Args:
            file_path: Path to the file
            file_type: Type of file ('photo', 'video', 'audio', 'document')
        
        Returns:
            file_id if successful, None otherwise
        """
        # If caching is disabled, return None
        if not self.file_id_cache or not self.cache_chat_id:
            return None
        
        # Check cache first
        file_id = self.file_id_cache.get_file_id(file_path)
        if file_id:
            return file_id
        
        # Not in cache, need to upload to cache chat
        try:
            with open(file_path, 'rb') as file_handle:
                if file_type == 'photo':
                    message = self.bot.send_photo(self.cache_chat_id, file_handle, protect_content=True)
                    file_id = message.photo[-1].file_id  # Get largest photo size
                elif file_type == 'video':
                    message = self.bot.send_video(self.cache_chat_id, file_handle, protect_content=True)
                    file_id = message.video.file_id
                elif file_type == 'audio':
                    message = self.bot.send_audio(self.cache_chat_id, file_handle, protect_content=True)
                    file_id = message.audio.file_id
                elif file_type == 'document':
                    message = self.bot.send_document(self.cache_chat_id, file_handle, protect_content=True)
                    file_id = message.document.file_id
                else:
                    return None
                
                # Store in cache
                self.file_id_cache.set_file_id(file_path, file_id)
                print(f"Cached file_id for {file_path} (type: {file_type})")
                return file_id
                
        except FileNotFoundError:
            print(f"File not found for caching: {file_path}")
            return None
        except Exception as e:
            print(f"Error uploading file to cache chat: {str(e)}")
            return None
    
    def _send_media_with_cache(
        self,
        chat_id: int,
        file_path: str,
        file_type: str,
        protect_content: bool = True
    ) -> bool:
        """
        Send media file using cache if available, otherwise upload directly.
        
        Args:
            chat_id: Telegram chat ID
            file_path: Path to the file
            file_type: Type of file ('photo', 'video', 'audio', 'document')
            protect_content: Whether to protect content from forwarding
        
        Returns:
            True if successful, False otherwise
        """
        # Try to get file_id from cache
        file_id = self._get_or_upload_file_id(file_path, file_type)
        
        if file_id:
            # Use cached file_id
            try:
                if file_type == 'photo':
                    self.bot.send_photo(chat_id, file_id, protect_content=protect_content)
                elif file_type == 'video':
                    self.bot.send_video(chat_id, file_id, protect_content=protect_content)
                elif file_type == 'audio':
                    self.bot.send_audio(chat_id, file_id, protect_content=protect_content)
                elif file_type == 'document':
                    self.bot.send_document(chat_id, file_id, protect_content=protect_content)
                else:
                    return False
                return True
            except Exception as e:
                # file_id might be invalid, remove from cache and fall back to upload
                error_str = str(e).lower()
                if 'file_id' in error_str or 'invalid' in error_str or 'bad request' in error_str:
                    print(f"Invalid file_id for {file_path}, removing from cache and re-uploading")
                    if self.file_id_cache:
                        self.file_id_cache.remove_file_id(file_path)
                    # Fall through to direct upload
        
        # Fall back to direct upload (cache miss or invalid file_id)
        try:
            with open(file_path, 'rb') as file_handle:
                if file_type == 'photo':
                    self.bot.send_photo(chat_id, file_handle, protect_content=protect_content)
                elif file_type == 'video':
                    self.bot.send_video(chat_id, file_handle, protect_content=protect_content)
                elif file_type == 'audio':
                    self.bot.send_audio(chat_id, file_handle, protect_content=protect_content)
                elif file_type == 'document':
                    self.bot.send_document(chat_id, file_handle, protect_content=protect_content)
                else:
                    return False
                return True
        except FileNotFoundError:
            print(f"Media file not found: {file_path}")
            return False
        except Exception as e:
            print(f"Error sending media file {file_path}: {str(e)}")
            return False
    
    def send_media_files(self, chat_id: int, media_paths: List[str]) -> bool:
        """
        Send media files (images, videos, audio) to user as protected content.
        
        Args:
            chat_id: Telegram chat ID
            media_paths: List of local file paths to media files
        
        Returns:
            True if all media files sent successfully, False otherwise
        """
        success = True
        for media_path in media_paths:
            if self._is_image_file(media_path):
                if not self._send_media_with_cache(chat_id, media_path, 'photo', protect_content=True):
                    success = False
            elif self._is_video_file(media_path):
                if not self._send_media_with_cache(chat_id, media_path, 'video', protect_content=True):
                    success = False
            elif self._is_audio_file(media_path):
                if not self._send_media_with_cache(chat_id, media_path, 'audio', protect_content=True):
                    success = False
            else:
                # Unknown media type, try sending as document
                print(f"Unknown media type for {media_path}, sending as document")
                if not self._send_media_with_cache(chat_id, media_path, 'document', protect_content=True):
                    success = False
        
        return success
    
    def send_document_files(self, chat_id: int, document_paths: List[str]) -> bool:
        """
        Send document files (.doc, .docx, .pdf) to user as unprotected attachments.
        
        Args:
            chat_id: Telegram chat ID
            document_paths: List of local file paths to document files
        
        Returns:
            True if all document files sent successfully, False otherwise
        """
        success = True
        for doc_path in document_paths:
            if not self._send_media_with_cache(chat_id, doc_path, 'document', protect_content=False):
                success = False
        
        return success
    
    def send_file_links(self, chat_id: int, files: List[Dict[str, str]]) -> bool:
        """
        Publish files as temporary public links and send them to user.
        
        Args:
            chat_id: Telegram chat ID
            files: List of file dictionaries with 'path' and 'name' keys
        
        Returns:
            True if all files processed successfully, False otherwise
        """
        if not files:
            return True
        
        success = True
        links_message = "📎 Доступные файлы:\n\n"
        links_sent = False
        
        for file_info in files:
            file_path = file_info.get('path')
            file_name = file_info.get('name', 'Файл')
            
            try:
                # Publish file as temporary public link (30 seconds expiration)
                result = self.disk_handler.publish_temporary_link(
                    file_path=file_path,
                    expiration_seconds=30
                )
                print(f"Published temporary link for {file_name} (expires in 30 seconds)")
                
                # Get public URL from result
                public_url = result.get('public_url')
                if not public_url:
                    # Fallback: try to get public URL directly
                    public_url = self.disk_handler._get_public_url(file_path)
                
                if public_url:
                    links_message += f"🔗 {file_name}\n{public_url}\n\n"
                    links_sent = True
                else:
                    links_message += f"⚠️ {file_name} - не удалось получить ссылку\n\n"
                    links_sent = True
                
            except APIError as e:
                print(f"Error publishing temporary link for {file_path}: {str(e)}")
                links_message += f"⚠️ {file_name} - ошибка доступа\n\n"
                links_sent = True
                success = False
            except Exception as e:
                print(f"Unexpected error with {file_path}: {str(e)}")
                links_message += f"⚠️ {file_name} - ошибка\n\n"
                links_sent = True
                success = False
        
        # Send links message if any links were processed
        if links_sent:
            try:
                self.bot.send_message(chat_id, links_message.strip(), parse_mode="HTML")
            except Exception as e:
                print(f"Error sending links message: {str(e)}")
                success = False
        
        return success
    
    def send_day_content(
        self,
        chat_id: int,
        content_data: Dict[str, Any]
    ) -> bool:
        """
        Send complete day content to user (text, media files, document files).
        
        Args:
            chat_id: Telegram chat ID
            content_data: Content data from ContentFetcher
        
        Returns:
            True if all content sent successfully, False otherwise
        """
        success = True
        
        # Send text content if available
        if content_data.get('text_content'):
            if not self.send_text_content(chat_id, content_data['text_content']):
                success = False
        
        # Send media files (images, videos, audio) as protected content
        if content_data.get('media_files'):
            if not self.send_media_files(chat_id, content_data['media_files']):
                success = False
        
        # Send document files (.doc, .docx, .pdf) as unprotected attachments
        if content_data.get('document_files'):
            if not self.send_document_files(chat_id, content_data['document_files']):
                success = False
        
        # Backward compatibility: support old format with image_paths and other_files
        # This allows gradual migration if needed
        if content_data.get('image_paths'):
            if not self.send_images(chat_id, content_data['image_paths']):
                success = False
        
        if content_data.get('other_files'):
            if not self.send_file_links(chat_id, content_data['other_files']):
                success = False
        
        return success
    
    def send_waiting_message(self, chat_id: int) -> bool:
        """
        Send "waiting for content" message.
        
        Args:
            chat_id: Telegram chat ID
        
        Returns:
            True if successful, False otherwise
        """
        message = "⏳ Контент для этого дня еще не готов. Пожалуйста, подождите."
        return self.send_text_content(chat_id, message)
    
    def send_error_message(self, chat_id: int, error_msg: str) -> bool:
        """
        Send error message to user.
        
        Args:
            chat_id: Telegram chat ID
            error_msg: Error message to send
        
        Returns:
            True if successful, False otherwise
        """
        message = f"❌ Ошибка: {error_msg}"
        return self.send_text_content(chat_id, message)
    
    def send_navigation_message(self, chat_id: int, text: str, reply_markup, parse_mode: str = "HTML") -> Optional[int]:
        """
        Send navigation message with inline keyboard.
        
        Args:
            chat_id: Telegram chat ID
            text: Message text (supports HTML formatting)
            reply_markup: Inline keyboard markup
            parse_mode: Parse mode for formatting ("HTML", "MarkdownV2", or None)
                       Defaults to "HTML" to support formatting in text files
        
        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message = self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
            return message.message_id
        except Exception as e:
            print(f"Error sending navigation message: {str(e)}")
            return None
    
    def edit_navigation_message(self, chat_id: int, message_id: int, text: str, reply_markup, parse_mode: str = "HTML") -> bool:
        """
        Edit existing navigation message.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            text: New message text (supports HTML formatting)
            reply_markup: New inline keyboard markup
            parse_mode: Parse mode for formatting ("HTML", "MarkdownV2", or None)
                       Defaults to "HTML" to support formatting in text files
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except telebot.apihelper.ApiTelegramException as e:
            # Handle specific Telegram API errors
            error_description = str(e).lower()
            if 'message is not modified' in error_description:
                # Message hasn't changed, but that's okay
                return True
            elif 'message to edit not found' in error_description or 'chat not found' in error_description:
                # Message was deleted
                print(f"Navigation message {message_id} not found (likely deleted)")
                return False
            else:
                print(f"Error editing navigation message: {str(e)}")
                return False
        except Exception as e:
            print(f"Error editing navigation message: {str(e)}")
            return False

