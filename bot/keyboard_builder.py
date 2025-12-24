"""
Keyboard Builder Module

Builds inline keyboards for day selection with pagination support.
"""

import math
from typing import List, Optional
import telebot.types as types


class KeyboardBuilder:
    """Builds paginated inline keyboards for day selection."""
    
    DAYS_PER_PAGE = 12  # Number of day buttons per page
    
    @staticmethod
    def build_day_selection_keyboard(
        available_days: List[int],
        current_page: int = 0,
        callback_prefix: str = "day_"
    ) -> types.InlineKeyboardMarkup:
        """
        Build paginated inline keyboard for day selection.
        
        Args:
            available_days: List of available day numbers (e.g., [1, 2, 3, 5, 7])
            current_page: Current page number (0-indexed)
            callback_prefix: Prefix for callback data (default: "day_")
        
        Returns:
            InlineKeyboardMarkup with day buttons and navigation
        """
        if not available_days:
            # No days available, return empty keyboard with a message
            keyboard = []
            return types.InlineKeyboardMarkup(keyboard)
        
        # Calculate pagination
        total_pages = math.ceil(len(available_days) / KeyboardBuilder.DAYS_PER_PAGE)
        current_page = max(0, min(current_page, total_pages - 1))  # Clamp to valid range
        
        # Get days for current page
        start_idx = current_page * KeyboardBuilder.DAYS_PER_PAGE
        end_idx = start_idx + KeyboardBuilder.DAYS_PER_PAGE
        page_days = available_days[start_idx:end_idx]
        
        # Build keyboard rows
        keyboard = []
        
        # Add day buttons (3 buttons per row for better layout)
        buttons_per_row = 3
        for i in range(0, len(page_days), buttons_per_row):
            row = page_days[i:i + buttons_per_row]
            keyboard_row = []
            for day_num in row:
                button_text = f"День {day_num}"
                callback_data = f"{callback_prefix}{day_num}"
                keyboard_row.append(types.InlineKeyboardButton(button_text, callback_data=callback_data))
            keyboard.append(keyboard_row)
        
        # Add navigation row
        nav_row = []
        
        # Previous button
        if current_page > 0:
            prev_callback = f"nav_prev_page_{current_page - 1}"
            nav_row.append(types.InlineKeyboardButton("◀️ Назад", callback_data=prev_callback))
        else:
            # Disabled state - we can't use disabled buttons in pyTelegramBotAPI, so we just don't add it
            pass
        
        # Page indicator
        if total_pages > 1:
            page_text = f"📄 {current_page + 1}/{total_pages}"
            nav_row.append(types.InlineKeyboardButton(page_text, callback_data="nav_page_info"))
        
        # Next button
        if current_page < total_pages - 1:
            next_callback = f"nav_next_page_{current_page + 1}"
            nav_row.append(types.InlineKeyboardButton("Вперёд ▶️", callback_data=next_callback))
        
        if nav_row:
            keyboard.append(nav_row)
        
        return types.InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def parse_callback_data(callback_data: str) -> Optional[dict]:
        """
        Parse callback data to extract action and parameters.
        
        Args:
            callback_data: Callback data string (e.g., "day_5", "nav_prev_page_1")
        
        Returns:
            Dictionary with 'action' and optional 'day_number' or 'page_number', or None if invalid
        """
        if callback_data.startswith("day_"):
            try:
                day_number = int(callback_data[4:])  # Extract number after "day_"
                return {'action': 'select_day', 'day_number': day_number}
            except ValueError:
                return None
        elif callback_data.startswith("nav_prev_page_"):
            try:
                page_number = int(callback_data[14:])  # Extract number after "nav_prev_page_"
                return {'action': 'prev_page', 'page_number': page_number}
            except ValueError:
                return None
        elif callback_data.startswith("nav_next_page_"):
            try:
                page_number = int(callback_data[14:])  # Extract number after "nav_next_page_"
                return {'action': 'next_page', 'page_number': page_number}
            except ValueError:
                return None
        elif callback_data == "nav_page_info":
            return {'action': 'page_info'}
        elif callback_data == "nav_main":
            return {'action': 'main_menu'}
        else:
            return None
    
    @staticmethod
    def build_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
        """
        Build main menu reply keyboard (custom keyboard widget).
        This keyboard hides the input field and provides always-accessible buttons.
        
        Returns:
            ReplyKeyboardMarkup with main menu buttons
        """
        # In pyTelegramBotAPI, create ReplyKeyboardMarkup and add buttons using row() method
        # The row() method accepts strings or KeyboardButton objects
        markup = types.ReplyKeyboardMarkup(
            resize_keyboard=True,  # Adjust keyboard size
            one_time_keyboard=False  # Keep keyboard visible
        )
        
        # Add buttons row by row (each row() call adds a new row)
        markup.row("📅 Выбрать день")
        markup.row("✏️ Изменить имя")
        
        return markup
    
    @staticmethod
    def remove_keyboard() -> types.ReplyKeyboardRemove:
        """
        Create ReplyKeyboardRemove to hide custom keyboard and show input field.
        
        Returns:
            ReplyKeyboardRemove object
        """
        return types.ReplyKeyboardRemove()
    
    @staticmethod
    def force_reply(placeholder: str = "Введите текст") -> types.ForceReply:
        """
        Create ForceReply to force show input field.
        
        Args:
            placeholder: Placeholder text for input field
        
        Returns:
            ForceReply object
        """
        # In pyTelegramBotAPI, ForceReply constructor signature:
        # ForceReply(force_reply=True, selective=False, input_field_placeholder=None)
        # Check if input_field_placeholder is supported
        try:
            return types.ForceReply(force_reply=True, input_field_placeholder=placeholder)
        except TypeError:
            # Fallback if input_field_placeholder is not supported
            return types.ForceReply(force_reply=True)

