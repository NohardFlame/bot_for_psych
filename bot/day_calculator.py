"""
Day Calculator Module

Calculates which day folder to access based on begin_date
"""

from datetime import datetime, date
from typing import Optional, List


class DayCalculator:
    """Calculates day folder name based on begin_date."""
    
    @staticmethod
    def parse_begin_date(date_str: str) -> Optional[date]:
        """
        Parse begin_date string to date object.
        
        Args:
            date_str: Date string in format "YYYY-MM-DD"
        
        Returns:
            date object if valid, None otherwise
        """
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def calculate_day_folder(begin_date_str: str, current_date: Optional[date] = None) -> Optional[str]:
        """
        Calculate day folder name based on begin_date.
        
        Day 1 = begin_date (inclusive)
        Day 2 = begin_date + 1 day
        etc.
        
        Args:
            begin_date_str: Begin date string in format "YYYY-MM-DD"
            current_date: Current date (defaults to today)
        
        Returns:
            Folder name like "1_day", "3_day", etc., or None if invalid
        """
        begin_date = DayCalculator.parse_begin_date(begin_date_str)
        if not begin_date:
            return None
        
        if current_date is None:
            current_date = date.today()
        
        # Calculate days difference (inclusive: day 1 = begin_date)
        days_diff = (current_date - begin_date).days + 1
        
        # Handle edge cases
        if days_diff < 1:
            # Future date or invalid
            return None
        
        return f"{days_diff}_day"
    
    @staticmethod
    def get_program_folder_path(program_key: str, day_folder: str) -> str:
        """
        Get full path to day folder on Yandex Disk.
        
        Args:
            program_key: Program key (e.g., "program_1")
            day_folder: Day folder name (e.g., "1_day")
        
        Returns:
            Full path like "disk:/program_1/1_day"
        """
        return f"disk:/{program_key}/{day_folder}"
    
    @staticmethod
    def calculate_days_to_deliver(
        begin_date_str: str,
        last_message_date: Optional[int],
        current_date: Optional[date] = None
    ) -> List[int]:
        """
        Calculate which day numbers should be delivered based on last_message_date.
        
        Args:
            begin_date_str: Begin date string in format "YYYY-MM-DD"
            last_message_date: Unix timestamp of last message date, or None if never delivered
            current_date: Current date (defaults to today)
        
        Returns:
            List of day numbers (e.g., [1, 2, 3]) that should be delivered
        """
        begin_date = DayCalculator.parse_begin_date(begin_date_str)
        if not begin_date:
            return []
        
        if current_date is None:
            current_date = date.today()
        
        # Calculate current day number
        current_day = (current_date - begin_date).days + 1
        if current_day < 1:
            return []  # Program hasn't started yet
        
        # If no last_message_date, deliver all days from 1 to current day
        if last_message_date is None:
            return list(range(1, current_day + 1))
        
        # Convert last_message_date timestamp to date
        try:
            last_date = datetime.fromtimestamp(last_message_date).date()
        except (ValueError, OSError):
            # Invalid timestamp, treat as never delivered
            return list(range(1, current_day + 1))
        
        # Calculate last delivered day number
        last_day = (last_date - begin_date).days + 1
        
        # If last_day is invalid or in the future, deliver all days
        if last_day < 1 or last_day > current_day:
            return list(range(1, current_day + 1))
        
        # Return days from (last_day + 1) to current_day
        if last_day >= current_day:
            return []  # Already up to date
        
        return list(range(last_day + 1, current_day + 1))

