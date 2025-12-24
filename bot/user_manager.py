"""
User Manager Module

Handles user registration, name storage, and management in handler_list.json
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class UserManager:
    """Manages user names and program assignments."""
    
    def __init__(self, handler_list_path: str = "handler_list.Json"):
        """
        Initialize UserManager.
        
        Args:
            handler_list_path: Path to handler_list.json file
        """
        self.handler_list_path = Path(handler_list_path)
        self._handler_data = None
        self._load_handler_list()
    
    def _load_handler_list(self) -> None:
        """Load handler_list.json into memory and migrate old format if needed."""
        if not self.handler_list_path.exists():
            raise FileNotFoundError(f"Handler list file not found: {self.handler_list_path}")
        
        with open(self.handler_list_path, 'r', encoding='utf-8') as f:
            self._handler_data = json.load(f)
        
        # Migrate old format to new format if needed
        self._migrate_old_format()
    
    def _migrate_old_format(self) -> None:
        """Migrate old format to new format (dict with name, chat_id, and last_message_date)."""
        migrated = False
        for program_key, program_data in self._handler_data.items():
            if not isinstance(program_data, dict):
                continue
            for key, value in list(program_data.items()):
                if key == 'begin_date':
                    continue
                if key.startswith('@'):
                    # Check if it's old format (string email/name)
                    if isinstance(value, str):
                        # Migrate to new format - use old email value as name
                        self._handler_data[program_key][key] = {
                            'name': value if value else '',
                            'chat_id': None,
                            'last_message_date': None
                        }
                        migrated = True
                    # Check if it has old 'email' field - migrate to 'name'
                    elif isinstance(value, dict):
                        if 'email' in value and 'name' not in value:
                            # Migrate email to name
                            value['name'] = value.pop('email', '')
                            migrated = True
                        # Check if it's missing last_message_date field
                        if 'last_message_date' not in value:
                            value['last_message_date'] = None
                            migrated = True
        
        if migrated:
            self._save_handler_list()
            print("Migrated handler_list.Json to new format (with name, chat_id and last_message_date support)")
    
    def _save_handler_list(self) -> None:
        """Save handler_list.json to disk."""
        with open(self.handler_list_path, 'w', encoding='utf-8') as f:
            json.dump(self._handler_data, f, indent=4, ensure_ascii=False)
    
    def validate_name(self, name: str) -> bool:
        """
        Validate that a name is provided (non-empty string).
        
        Args:
            name: Name to validate
        
        Returns:
            True if the name is valid (non-empty), False otherwise
        """
        return bool(name and isinstance(name, str) and name.strip())
    
    def find_user_program(self, username: str) -> Optional[str]:
        """
        Find which program key contains the user.
        
        Args:
            username: Telegram username (e.g., "@NohardFlame")
        
        Returns:
            Program key (e.g., "program_1") if found, None otherwise
        """
        if not username.startswith('@'):
            username = '@' + username
        
        for program_key, program_data in self._handler_data.items():
            if not isinstance(program_data, dict):
                continue
            if username in program_data:
                return program_key
        
        return None
    
    def _get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user data structure (handles both old and new format).
        
        Args:
            username: Telegram username
        
        Returns:
            User data dict with 'name' and 'chat_id', or None if not found
        """
        program_key = self.find_user_program(username)
        if not program_key:
            return None
        
        if not username.startswith('@'):
            username = '@' + username
        
        user_data = self._handler_data[program_key].get(username)
        if user_data is None:
            return None
        
        # Handle old format (string email/name)
        if isinstance(user_data, str):
            return {'name': user_data if user_data else '', 'chat_id': None, 'last_message_date': None}
        
        # Handle new format (dict)
        if isinstance(user_data, dict):
            # Support migration from 'email' to 'name'
            name = user_data.get('name', '')
            if not name and 'email' in user_data:
                name = user_data.get('email', '')
            return {
                'name': name,
                'chat_id': user_data.get('chat_id'),
                'last_message_date': user_data.get('last_message_date')
            }
        
        return None
    
    def is_user_registered(self, username: str) -> bool:
        """
        Check if user exists in handler_list.json.
        
        Args:
            username: Telegram username
        
        Returns:
            True if user is registered, False otherwise
        """
        return self.find_user_program(username) is not None
    
    def get_user_name(self, username: str) -> Optional[str]:
        """
        Get user's name from handler_list.json.
        
        Args:
            username: Telegram username
        
        Returns:
            Name if set, None if not set or user not found
        """
        user_data = self._get_user_data(username)
        if not user_data:
            return None
        
        name = user_data.get('name', '')
        return name if name else None
    
    def get_user_chat_id(self, username: str) -> Optional[int]:
        """
        Get user's chat_id from handler_list.json.
        
        Args:
            username: Telegram username
        
        Returns:
            Chat ID if set, None if not set or user not found
        """
        user_data = self._get_user_data(username)
        if not user_data:
            return None
        
        return user_data.get('chat_id')
    
    def set_user_chat_id(self, username: str, chat_id: int) -> bool:
        """
        Set or update user's chat_id in handler_list.json.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
        
        Returns:
            True if successful, False if user not found
        """
        program_key = self.find_user_program(username)
        if not program_key:
            return False
        
        if not username.startswith('@'):
            username = '@' + username
        
        # Ensure user data is in new format
        user_data = self._get_user_data(username)
        if user_data is None:
            return False
        
        # Update chat_id
        if not isinstance(self._handler_data[program_key][username], dict):
            # Convert to new format if needed
            name = user_data.get('name', '')
            last_message_date = user_data.get('last_message_date')
            self._handler_data[program_key][username] = {
                'name': name,
                'chat_id': chat_id,
                'last_message_date': last_message_date
            }
        else:
            self._handler_data[program_key][username]['chat_id'] = chat_id
            # Ensure last_message_date exists
            if 'last_message_date' not in self._handler_data[program_key][username]:
                self._handler_data[program_key][username]['last_message_date'] = None
        
        self._save_handler_list()
        return True
    
    def set_user_name(self, username: str, name: str) -> bool:
        """
        Set or update user's name in handler_list.json.
        
        Args:
            username: Telegram username
            name: User's name
        
        Returns:
            True if successful, False if validation fails or user not found
        """
        if not self.validate_name(name):
            return False
        
        program_key = self.find_user_program(username)
        if not program_key:
            return False
        
        if not username.startswith('@'):
            username = '@' + username
        
        # Get existing chat_id and last_message_date if any
        user_data = self._get_user_data(username)
        chat_id = user_data.get('chat_id') if user_data else None
        last_message_date = user_data.get('last_message_date') if user_data else None
        
        # Update in new format
        self._handler_data[program_key][username] = {
            'name': name.strip(),
            'chat_id': chat_id,
            'last_message_date': last_message_date
        }
        
        self._save_handler_list()
        return True
    
    def get_all_users_with_chat_ids(self) -> Dict[str, int]:
        """
        Get all users with their chat_ids for scheduler.
        
        Returns:
            Dictionary mapping username to chat_id (only users with chat_id set)
        """
        user_chat_map = {}
        for program_key, program_data in self._handler_data.items():
            if not isinstance(program_data, dict):
                continue
            for key, value in program_data.items():
                if key == 'begin_date':
                    continue
                if key.startswith('@'):
                    user_data = self._get_user_data(key)
                    if user_data and user_data.get('chat_id'):
                        user_chat_map[key] = user_data['chat_id']
        
        return user_chat_map
    
    def get_program_data(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get program data for a user (including begin_date).
        
        Args:
            username: Telegram username
        
        Returns:
            Program data dictionary if found, None otherwise
        """
        program_key = self.find_user_program(username)
        if not program_key:
            return None
        
        return self._handler_data[program_key].copy()
    
    def needs_name(self, username: str) -> bool:
        """
        Check if user needs to provide a name (name is empty).
        
        Args:
            username: Telegram username
        
        Returns:
            True if name is needed, False otherwise
        """
        name = self.get_user_name(username)
        return name is None
    
    def get_user_last_message_date(self, username: str) -> Optional[int]:
        """
        Get user's last_message_date from handler_list.json.
        
        Args:
            username: Telegram username
        
        Returns:
            Unix timestamp (seconds since epoch) if set, None if not set or user not found
        """
        user_data = self._get_user_data(username)
        if not user_data:
            return None
        
        return user_data.get('last_message_date')
    
    def set_user_last_message_date(self, username: str, timestamp: int) -> bool:
        """
        Set or update user's last_message_date in handler_list.json.
        
        Args:
            username: Telegram username
            timestamp: Unix timestamp (seconds since epoch)
        
        Returns:
            True if successful, False if user not found
        """
        program_key = self.find_user_program(username)
        if not program_key:
            return False
        
        if not username.startswith('@'):
            username = '@' + username
        
        # Ensure user data is in new format
        user_data = self._get_user_data(username)
        if user_data is None:
            return False
        
        # Update last_message_date
        if not isinstance(self._handler_data[program_key][username], dict):
            # Convert to new format if needed
            name = user_data.get('name', '')
            chat_id = user_data.get('chat_id')
            self._handler_data[program_key][username] = {
                'name': name,
                'chat_id': chat_id,
                'last_message_date': timestamp
            }
        else:
            self._handler_data[program_key][username]['last_message_date'] = timestamp
        
        self._save_handler_list()
        return True
    
    def update_user_last_message_date(self, username: str, day_number: int, begin_date: str) -> bool:
        """
        Calculate and set last_message_date based on day number and begin_date.
        
        Args:
            username: Telegram username
            day_number: Day number (1, 2, 3, etc.)
            begin_date: Begin date string in format "YYYY-MM-DD"
        
        Returns:
            True if successful, False otherwise
        """
        from datetime import datetime, timedelta
        
        try:
            begin_date_obj = datetime.strptime(begin_date, "%Y-%m-%d").date()
            # Calculate the date for this day (day 1 = begin_date, day 2 = begin_date + 1, etc.)
            message_date = begin_date_obj + timedelta(days=day_number - 1)
            # Convert to Unix timestamp (end of day to ensure we've delivered that day's content)
            message_datetime = datetime.combine(message_date, datetime.max.time())
            timestamp = int(message_datetime.timestamp())
            
            return self.set_user_last_message_date(username, timestamp)
        except (ValueError, TypeError) as e:
            print(f"Error calculating last_message_date for {username}: {e}")
            return False

