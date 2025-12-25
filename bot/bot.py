"""
Main Telegram Bot

Entry point for the Telegram bot that delivers daily content from Yandex Disk
"""

import telebot
import configparser
from pathlib import Path
from typing import Dict, Optional

# Handle both package and direct execution
try:
    from .user_manager import UserManager
    from .day_calculator import DayCalculator
    from .content_fetcher import ContentFetcher
    from .content_sender import ContentSender
    from .scheduler import ContentScheduler
    from .file_id_cache import FileIdCache
    from .keyboard_builder import KeyboardBuilder
    from .present_navigator import PresentNavigator
except ImportError:
    from user_manager import UserManager
    from day_calculator import DayCalculator
    from content_fetcher import ContentFetcher
    from content_sender import ContentSender
    from scheduler import ContentScheduler
    from file_id_cache import FileIdCache
    from keyboard_builder import KeyboardBuilder
    from present_navigator import PresentNavigator

from disk_api_handler.disk_handler import YandexDiskHandler


class DailyContentBot:
    """Main bot class for daily content delivery."""
    
    def __init__(self, bot_token_path: str = "bot_token.txt", bot_token: Optional[str] = None, disk_token: Optional[str] = None):
        """
        Initialize the bot.
        
        Args:
            bot_token_path: Path to file containing bot token (used if bot_token is not provided)
            bot_token: Optional bot token string. If provided, uses this token directly
                      instead of reading from file.
            disk_token: Optional Yandex Disk token string. If provided, uses this token directly
                       instead of reading from file.
        """
        # Load bot token
        if bot_token is not None:
            if not bot_token.strip():
                raise ValueError("Bot token is empty")
            bot_token_value = bot_token.strip()
        else:
            token_path = Path(bot_token_path)
            if not token_path.exists():
                raise FileNotFoundError(f"Bot token file not found: {bot_token_path}")
            
            with open(token_path, 'r', encoding='utf-8') as f:
                bot_token_value = f.read().strip()
            
            if not bot_token_value:
                raise ValueError("Bot token is empty")
        
        # Initialize bot
        self.bot = telebot.TeleBot(bot_token_value)
        
        # Initialize file ID cache
        self.file_id_cache = FileIdCache()
        
        # Get cache chat ID from settings or use None (disables caching)
        cache_chat_id = self._get_cache_chat_id()
        if cache_chat_id is None:
            print("File caching is disabled. To enable, add cache_chat_id to [bot] section in settings.ini")
        else:
            print(f"File caching enabled with cache_chat_id: {cache_chat_id}")
        
        # Initialize modules
        self.user_manager = UserManager()
        if disk_token is not None:
            self.disk_handler = YandexDiskHandler(token=disk_token)
        else:
            self.disk_handler = YandexDiskHandler()
        self.day_calculator = DayCalculator()
        self.content_fetcher = ContentFetcher(self.disk_handler)
        self.content_sender = ContentSender(
            self.bot,
            self.disk_handler,
            file_id_cache=self.file_id_cache,
            cache_chat_id=cache_chat_id
        )
        
        # Track user states (for name input)
        self.user_states: Dict[int, str] = {}  # chat_id -> state
        
        # Track chat_ids for scheduler (username -> chat_id)
        self.user_chat_map: Dict[str, int] = {}
        
        # Track navigation message IDs per user (chat_id -> message_id)
        self.navigation_messages: Dict[int, int] = {}  # chat_id -> message_id
        
        # Track present folder navigation breadcrumbs per user (chat_id -> list of paths)
        self.present_navigation_paths: Dict[int, list] = {}  # chat_id -> [path1, path2, ...]
        
        # Initialize scheduler (default: 9:00 AM, configurable)
        from datetime import time as dt_time
        self.scheduler = ContentScheduler(
            self.bot,
            self.user_manager,
            self.disk_handler,
            delivery_time=dt_time(9, 0),  # 9:00 AM default, can be changed via set_delivery_time()
            file_id_cache=self.file_id_cache,
            cache_chat_id=cache_chat_id
        )
        
        # Register handlers
        self._register_handlers()
    
    def _show_navigation_keyboard(self, username: str, chat_id: int, page: int = 0) -> None:
        """
        Show or update navigation keyboard with available days.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
            page: Page number (0-indexed) for pagination
        """
        try:
            # Get program data
            program_data = self.user_manager.get_program_data(username)
            if not program_data:
                self.bot.send_message(chat_id, "❌ Ошибка: программа не найдена", parse_mode="HTML")
                return
            
            program_key = self.user_manager.find_user_program(username)
            begin_date = program_data.get('begin_date')
            
            if not begin_date:
                self.bot.send_message(chat_id, "❌ Ошибка: дата начала не найдена", parse_mode="HTML")
                return
            
            # Calculate current day number based on begin_date
            begin_date_obj = self.day_calculator.parse_begin_date(begin_date)
            if not begin_date_obj:
                self.bot.send_message(chat_id, "❌ Ошибка: неверная дата начала", parse_mode="HTML")
                return
            
            from datetime import date as dt_date
            current_date = dt_date.today()
            current_day = (current_date - begin_date_obj).days + 1
            if current_day < 1:
                current_day = 1  # At least show day 1
            
            # Get available days from disk
            available_days = self.content_fetcher.get_available_days(program_key, current_day)
            
            if not available_days:
                self.bot.send_message(
                    chat_id,
                    "📭 Пока нет доступных дней программы. Контент появится позже.",
                    parse_mode="HTML"
                )
                return
            
            # Build keyboard
            keyboard = KeyboardBuilder.build_day_selection_keyboard(available_days, page)
            
            # Build message text
            message_text = (
                f"📅 Выберите день программы:\n\n"
                f"Доступно дней: {len(available_days)}\n"
                f"Используйте кнопки ниже для выбора."
            )
            
            # Update or send navigation message
            if chat_id in self.navigation_messages:
                # Try to edit existing message
                message_id = self.navigation_messages[chat_id]
                try:
                    success = self.content_sender.edit_navigation_message(
                        chat_id, message_id, message_text, keyboard
                    )
                    if not success:
                        # Message might have been deleted, send new one
                        new_message_id = self.content_sender.send_navigation_message(
                            chat_id, message_text, keyboard
                        )
                        if new_message_id:
                            self.navigation_messages[chat_id] = new_message_id
                except Exception as e:
                    # Error editing message (e.g., message was deleted), send new one
                    print(f"Error editing navigation message: {str(e)}")
                    new_message_id = self.content_sender.send_navigation_message(
                        chat_id, message_text, keyboard
                    )
                    if new_message_id:
                        self.navigation_messages[chat_id] = new_message_id
            else:
                # Send new message
                new_message_id = self.content_sender.send_navigation_message(
                    chat_id, message_text, keyboard
                )
                if new_message_id:
                    self.navigation_messages[chat_id] = new_message_id
                    
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {str(e)}"
            print(error_msg)
            self.bot.send_message(chat_id, f"❌ {error_msg}", parse_mode="HTML")
    
    def _deliver_single_day(self, username: str, chat_id: int, day_number: int) -> bool:
        """
        Deliver content for a single day.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
            day_number: Day number to deliver
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get program data
            program_data = self.user_manager.get_program_data(username)
            if not program_data:
                return False
            
            program_key = self.user_manager.find_user_program(username)
            begin_date = program_data.get('begin_date')
            
            if not begin_date:
                return False
            
            # Calculate day folder for this day
            day_folder = f"{day_number}_day"
            
            # Get folder path
            folder_path = self.day_calculator.get_program_folder_path(program_key, day_folder)
            
            # Fetch content
            content_data = self.content_fetcher.fetch_day_content(folder_path)
            
            # Check for errors
            if content_data.get('error'):
                error_msg = content_data['error']
                if error_msg == "Day folder not found":
                    return False
                else:
                    return False
            
            # Send content
            success = self.content_sender.send_day_content(chat_id, content_data)
            if success:
                # Update last_message_date (optional - we might want to track which days were viewed)
                # For now, we'll just update it to the day that was delivered
                self.user_manager.update_user_last_message_date(username, day_number, begin_date)
            
            return success
            
        except Exception as e:
            error_msg = f"Ошибка при доставке дня {day_number}: {str(e)}"
            print(error_msg)
            return False
    
    def _handle_present_folder_navigation(self, chat_id: int, folder_path: str = "") -> None:
        """
        Handle present folder navigation - display message and folder buttons.
        
        Args:
            chat_id: Telegram chat ID
            folder_path: Relative path within present folder (empty for root)
        """
        try:
            # Validate folder path for security
            if not PresentNavigator.validate_folder_path(folder_path):
                self.bot.send_message(chat_id, "❌ Неверный путь. Доступ запрещен.", parse_mode="HTML")
                return
            
            # Read message from folder
            message_text = PresentNavigator.get_folder_message(self.disk_handler, folder_path)
            if not message_text:
                message_text = "📁"  # Default message if msg.txt doesn't exist
            
            # Get subfolders
            subfolders = PresentNavigator.get_subfolders(self.disk_handler, folder_path)
            
            # Determine if there's a parent folder (for back button)
            has_parent = bool(folder_path and folder_path.strip() != "/")
            
            # Build keyboard
            keyboard = KeyboardBuilder.build_present_folder_keyboard(
                subfolders,
                current_path=folder_path,
                has_parent=has_parent
            )
            
            # Update breadcrumb trail
            if chat_id not in self.present_navigation_paths:
                self.present_navigation_paths[chat_id] = []
            
            breadcrumb = self.present_navigation_paths[chat_id]
            
            # Build breadcrumb from folder_path (e.g., "option1/option2" -> ["option1", "option1/option2"])
            if folder_path:
                # Split path into components and build cumulative paths
                parts = folder_path.strip('/').split('/')
                new_breadcrumb = []
                current_path = ""
                for part in parts:
                    if current_path:
                        current_path = f"{current_path}/{part}"
                    else:
                        current_path = part
                    new_breadcrumb.append(current_path)
                self.present_navigation_paths[chat_id] = new_breadcrumb
            else:
                # Root folder
                self.present_navigation_paths[chat_id] = []
            
            # Send or edit message
            # Try to edit existing message if it exists in navigation_messages
            if chat_id in self.navigation_messages:
                message_id = self.navigation_messages[chat_id]
                try:
                    self.bot.edit_message_text(
                        message_text if message_text else "📁",
                        chat_id,
                        message_id,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                    return
                except Exception:
                    # Message might have been deleted or can't be edited, send new one
                    pass
            
            # Send new message
            sent_message = self.bot.send_message(
                chat_id,
                message_text if message_text else "📁",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            if sent_message:
                self.navigation_messages[chat_id] = sent_message.message_id
                
        except Exception as e:
            error_msg = f"Ошибка при навигации: {str(e)}"
            print(error_msg)
            self.bot.send_message(chat_id, f"❌ {error_msg}", parse_mode="HTML")
    
    def _register_handlers(self) -> None:
        """Register all bot handlers."""
        
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            """Handle /start command."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            # Check for deep link parameter (p=)
            # Format: /start p=option1 or /start p=option1/option2 or /start p= (for root)
            command_text = message.text or ""
            folder_path = ""
            has_p_param = False
            
            if "p=" in command_text:
                has_p_param = True
                # Extract path after p=
                parts = command_text.split("p=", 1)
                if len(parts) > 1:
                    folder_path = parts[1].strip()
                    # Remove any extra spaces or newlines
                    folder_path = folder_path.split()[0] if folder_path.split() else ""
            
            # If deep link parameter is present (even if empty), handle present folder navigation (public access)
            if has_p_param:
                # Public access - no registration required for present folder navigation
                # Handle present folder navigation (empty folder_path means root)
                self._handle_present_folder_navigation(chat_id, folder_path)
                return
            
            # Normal bot flow (requires registration)
            if not username:
                self.bot.reply_to(
                    message,
                    "❌ Для использования бота необходимо установить username в настройках Telegram."
                )
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.reply_to(
                    message,
                    "❌ Доступ запрещен. Ваш username не найден в системе."
                )
                return
            
            # Check if name is needed
            if self.user_manager.needs_name(username):
                # Show input field for name input
                self.bot.reply_to(
                    message,
                    "👋 Добро пожаловать!\n\n"
                    "Для продолжения работы необходимо указать ваше имя.\n"
                    "Пожалуйста, введите ваше имя в поле ниже:",
                    reply_markup=KeyboardBuilder.force_reply("Введите ваше имя")
                )
                self.user_states[chat_id] = "waiting_name"
            else:
                # Show main menu widget (hides input field)
                self.bot.reply_to(
                    message,
                    "👋 Добро пожаловать!\n\n"
                    "Используйте кнопки ниже для навигации.",
                    reply_markup=KeyboardBuilder.build_main_menu_keyboard()
                )
        
        @self.bot.message_handler(commands=['set_name'])
        def handle_set_name(message):
            """Handle /set_name command."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            if not username:
                self.bot.reply_to(
                    message,
                    "❌ Для использования бота необходимо установить username в настройках Telegram."
                )
                return
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.reply_to(
                    message,
                    "❌ Доступ запрещен. Ваш username не найден в системе."
                )
                return
            
            # Parse name from command
            command_parts = message.text.split(maxsplit=1)
            if len(command_parts) > 1:
                name = command_parts[1].strip()
                if self.user_manager.set_user_name(username, name):
                    self.bot.reply_to(
                        message,
                        f"✅ Имя успешно установлено: {name}\n\n"
                        "Теперь вы можете использовать кнопки ниже для навигации.",
                        reply_markup=KeyboardBuilder.build_main_menu_keyboard()
                    )
                    self.user_states.pop(chat_id, None)
                else:
                    self.bot.reply_to(
                        message,
                        "❌ Имя не может быть пустым. Пожалуйста, укажите ваше имя."
                    )
            else:
                # Show input field for name input
                self.bot.reply_to(
                    message,
                    "👤 Пожалуйста, введите ваше имя в поле ниже:",
                    reply_markup=KeyboardBuilder.force_reply("Введите ваше имя")
                )
                self.user_states[chat_id] = "waiting_name"
        
        @self.bot.message_handler(commands=['get_name'])
        def handle_get_name(message):
            """Handle /get_name command - show input field for name input."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            if not username:
                self.bot.reply_to(
                    message,
                    "❌ Для использования бота необходимо установить username в настройках Telegram."
                )
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.reply_to(
                    message,
                    "❌ Доступ запрещен. Ваш username не найден в системе."
                )
                return
            
            # Show input field for name input
            self.bot.reply_to(
                message,
                "👤 Пожалуйста, введите ваше имя в поле ниже:",
                reply_markup=KeyboardBuilder.force_reply("Введите ваше имя")
            )
            self.user_states[chat_id] = "waiting_name"
        
        @self.bot.message_handler(commands=['get_day'])
        def handle_get_day(message):
            """Handle /get_day command - show navigation keyboard."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            if not username:
                self.bot.reply_to(
                    message,
                    "❌ Для использования бота необходимо установить username в настройках Telegram."
                )
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.reply_to(
                    message,
                    "❌ Доступ запрещен. Ваш username не найден в системе."
                )
                return
            
            # Check if name is set
            user_name = self.user_manager.get_user_name(username)
            if not user_name:
                self.bot.reply_to(
                    message,
                    "❌ Необходимо указать имя. Используйте /set_name <имя>"
                )
                return
            
            # Show navigation keyboard instead of auto-delivering
            # Keep main menu widget visible
            self._show_navigation_keyboard(username, chat_id, page=0)
        
        @self.bot.message_handler(func=lambda message: message.text in ["📅 Выбрать день", "✏️ Изменить имя"])
        def handle_main_menu_button(message):
            """Handle main menu button clicks."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            if not username:
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.reply_to(
                    message,
                    "❌ Доступ запрещен. Ваш username не найден в системе."
                )
                return
            
            button_text = message.text
            
            if button_text == "📅 Выбрать день":
                # Check if name is set
                user_name = self.user_manager.get_user_name(username)
                if not user_name:
                    self.bot.reply_to(
                        message,
                        "❌ Необходимо указать имя. Нажмите '✏️ Изменить имя' для ввода имени.",
                        reply_markup=KeyboardBuilder.build_main_menu_keyboard()
                    )
                    return
                
                # Show navigation keyboard
                self._show_navigation_keyboard(username, chat_id, page=0)
            
            elif button_text == "✏️ Изменить имя":
                # Show input field for name input
                self.bot.reply_to(
                    message,
                    "👤 Пожалуйста, введите ваше имя в поле ниже:",
                    reply_markup=KeyboardBuilder.force_reply("Введите ваше имя")
                )
                self.user_states[chat_id] = "waiting_name"
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback_query(call):
            """Handle callback queries from inline keyboards."""
            chat_id = call.message.chat.id
            username = call.from_user.username
            callback_data = call.data
            
            # Check if this is a present folder navigation callback (public access)
            present_parsed = KeyboardBuilder.parse_present_callback_data(callback_data)
            if present_parsed:
                # Present folder navigation - public access, no registration required
                action = present_parsed.get('action')
                
                # Answer callback query (required by Telegram)
                self.bot.answer_callback_query(call.id)
                
                try:
                    if action == 'present_folder':
                        # User selected a folder
                        folder_path = present_parsed.get('folder_path', '')
                        self._handle_present_folder_navigation(chat_id, folder_path)
                    
                    elif action == 'present_back':
                        # User clicked back button
                        if chat_id in self.present_navigation_paths and self.present_navigation_paths[chat_id]:
                            # Remove current path from breadcrumb
                            breadcrumb = self.present_navigation_paths[chat_id]
                            breadcrumb.pop()  # Remove current
                            
                            # Get parent path
                            if breadcrumb:
                                parent_path = breadcrumb[-1]
                            else:
                                parent_path = ""  # Back to root
                            
                            # Navigate to parent
                            self._handle_present_folder_navigation(chat_id, parent_path)
                        else:
                            # No breadcrumb, go to root
                            self._handle_present_folder_navigation(chat_id, "")
                    
                except Exception as e:
                    error_msg = f"Ошибка навигации: {str(e)}"
                    print(error_msg)
                    self.bot.send_message(chat_id, f"❌ {error_msg}", parse_mode="HTML")
                
                return  # Exit early for present folder callbacks
            
            # Normal bot flow callbacks (require registration)
            if not username:
                self.bot.answer_callback_query(call.id, "❌ Username не установлен")
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                self.bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            # Check if name is set
            user_name = self.user_manager.get_user_name(username)
            if not user_name:
                self.bot.answer_callback_query(call.id, "❌ Необходимо указать имя")
                return
            
            # Parse callback data
            try:
                parsed = KeyboardBuilder.parse_callback_data(callback_data)
                if not parsed:
                    self.bot.answer_callback_query(call.id, "❌ Неверная команда")
                    return
            except Exception as e:
                print(f"Error parsing callback data: {str(e)}")
                self.bot.answer_callback_query(call.id, "❌ Ошибка обработки команды")
                return
            
            action = parsed.get('action')
            
            # Answer callback query (required by Telegram)
            self.bot.answer_callback_query(call.id)
            
            try:
                if action == 'select_day':
                    # User selected a day
                    day_number = parsed.get('day_number')
                    if day_number:
                        # Show loading message
                        loading_msg = self.bot.send_message(chat_id, f"⏳ Загрузка контента для дня {day_number}...", parse_mode="HTML")
                        
                        # Deliver content for selected day
                        success = self._deliver_single_day(username, chat_id, day_number)
                        
                        # Delete loading message
                        try:
                            self.bot.delete_message(chat_id, loading_msg.message_id)
                        except Exception:
                            pass
                        
                        if not success:
                            self.bot.send_message(
                                chat_id,
                                f"❌ Не удалось загрузить контент для дня {day_number}. Возможно, контент еще не готов.",
                                parse_mode="HTML"
                            )
                
                elif action in ('prev_page', 'next_page'):
                    # Navigation - change page
                    page_number = parsed.get('page_number', 0)
                    if page_number < 0:
                        page_number = 0
                    self._show_navigation_keyboard(username, chat_id, page=page_number)
                
                elif action == 'page_info':
                    # User clicked page info - do nothing, just answer callback
                    pass
                
                elif action == 'main_menu':
                    # Return to main navigation (page 0)
                    self._show_navigation_keyboard(username, chat_id, page=0)
                    
            except Exception as e:
                error_msg = f"Ошибка: {str(e)}"
                print(error_msg)
                self.bot.send_message(chat_id, f"❌ {error_msg}", parse_mode="HTML")
        
        @self.bot.message_handler(func=lambda message: True)
        def handle_message(message):
            """Handle all other messages (for name input)."""
            chat_id = message.chat.id
            username = message.from_user.username
            
            if not username:
                return
            
            # Store chat_id
            self.update_user_chat_map(username, chat_id)
            
            # Check if we're waiting for name
            if chat_id in self.user_states and self.user_states[chat_id] == "waiting_name":
                name = message.text.strip()
                
                if self.user_manager.set_user_name(username, name):
                    self.bot.reply_to(
                        message,
                        f"✅ Имя успешно установлено: {name}\n\n"
                        "Теперь вы можете использовать кнопки ниже для навигации.",
                        reply_markup=KeyboardBuilder.build_main_menu_keyboard()
                    )
                    self.user_states.pop(chat_id, None)
                else:
                    self.bot.reply_to(
                        message,
                        "❌ Имя не может быть пустым. Пожалуйста, укажите ваше имя."
                    )
    
    def _deliver_content_to_user(self, username: str, chat_id: int, message=None) -> None:
        """
        Deliver content to a specific user.
        Checks last_message_date and delivers all missing days.
        Updates timestamp immediately after each successful day delivery.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
            message: Optional message object for replying
        """
        try:
            # Get program data
            program_data = self.user_manager.get_program_data(username)
            if not program_data:
                if message:
                    self.bot.reply_to(message, "❌ Ошибка: программа не найдена")
                return
            
            program_key = self.user_manager.find_user_program(username)
            begin_date = program_data.get('begin_date')
            
            if not begin_date:
                if message:
                    self.bot.reply_to(message, "❌ Ошибка: дата начала не найдена")
                return
            
            # Get user's last_message_date
            last_message_date = self.user_manager.get_user_last_message_date(username)
            
            # Calculate which days need to be delivered
            days_to_deliver = self.day_calculator.calculate_days_to_deliver(
                begin_date,
                last_message_date
            )
            
            if not days_to_deliver:
                # User is up to date
                if message:
                    self.bot.reply_to(message, "✅ Вы уже получили весь доступный контент.")
                return
            
            # Send "processing" message
            if message:
                if len(days_to_deliver) > 1:
                    processing_msg = self.bot.reply_to(
                        message,
                        f"⏳ Загрузка контента для {len(days_to_deliver)} дней..."
                    )
                else:
                    processing_msg = self.bot.reply_to(message, "⏳ Загрузка контента...")
            else:
                processing_msg = None
            
            # Deliver each day in sequence
            at_least_one_success = False
            failed_days = []
            
            for day_number in days_to_deliver:
                try:
                    # Calculate day folder for this day
                    day_folder = f"{day_number}_day"
                    
                    # Get folder path
                    folder_path = self.day_calculator.get_program_folder_path(program_key, day_folder)
                    
                    # Fetch content
                    content_data = self.content_fetcher.fetch_day_content(folder_path)
                    
                    # Check for errors
                    if content_data.get('error'):
                        error_msg = content_data['error']
                        if error_msg == "Day folder not found":
                            # Day not ready yet, skip it (don't update timestamp)
                            failed_days.append(day_number)
                            continue
                        else:
                            # Other error, skip this day
                            failed_days.append(day_number)
                            continue
                    
                    # Send content
                    success = self.content_sender.send_day_content(chat_id, content_data)
                    if not success:
                        # Failed to send, don't update timestamp
                        failed_days.append(day_number)
                        continue
                    
                    # Success! Update last_message_date immediately
                    self.user_manager.update_user_last_message_date(username, day_number, begin_date)
                    at_least_one_success = True
                    
                except Exception as e:
                    # Error delivering this day, continue with next day
                    error_msg = f"Ошибка при доставке дня {day_number}: {str(e)}"
                    print(error_msg)
                    failed_days.append(day_number)
                    continue
            
            # Delete processing message
            if processing_msg:
                try:
                    self.bot.delete_message(chat_id, processing_msg.message_id)
                except Exception:
                    pass
            
            # Report results
            if at_least_one_success:
                if failed_days:
                    if message:
                        self.bot.reply_to(
                            message,
                            f"✅ Контент доставлен. Не удалось доставить дни: {', '.join(map(str, failed_days))}"
                        )
                # If all succeeded, no message needed (content was already sent)
            else:
                # All days failed
                if message:
                    self.bot.reply_to(
                        message,
                        f"❌ Не удалось доставить контент для дней: {', '.join(map(str, failed_days))}"
                    )
                else:
                    self.content_sender.send_error_message(
                        chat_id,
                        f"Не удалось доставить контент для дней: {', '.join(map(str, failed_days))}"
                    )
            
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {str(e)}"
            print(error_msg)
            if message:
                self.bot.reply_to(message, f"❌ {error_msg}")
            else:
                self.content_sender.send_error_message(chat_id, error_msg)
    
    def start(self) -> None:
        """Start the bot and scheduler."""
        print("Starting bot...")
        
        # Load user_chat_map from handler_list.Json (persisted chat_ids)
        persisted_chat_map = self.user_manager.get_all_users_with_chat_ids()
        self.user_chat_map.update(persisted_chat_map)
        
        if persisted_chat_map:
            print(f"Loaded {len(persisted_chat_map)} users with chat_ids from handler_list.Json")
        
        # Start scheduler (with persisted user_chat_map)
        # Note: scheduler will update as users interact with bot
        self.scheduler.start(self.user_chat_map)
        
        print("Bot is running. Press Ctrl+C to stop.")
        try:
            self.bot.infinity_polling()
        except KeyboardInterrupt:
            print("\nStopping bot...")
            self.stop()
            print("Bot stopped.")
    
    def stop(self) -> None:
        """Stop the bot and scheduler gracefully."""
        # Stop scheduler first
        if hasattr(self, 'scheduler') and self.scheduler:
            self.scheduler.stop()
        
        # Stop bot polling
        if hasattr(self, 'bot') and self.bot:
            try:
                # Try to stop polling gracefully
                if hasattr(self.bot, 'stop_polling'):
                    self.bot.stop_polling()
                elif hasattr(self.bot, 'stop_bot'):
                    self.bot.stop_bot()
            except Exception as e:
                # If stopping fails, log but continue
                print(f"Warning: Could not stop bot gracefully: {str(e)}")
    
    def _get_cache_chat_id(self) -> Optional[int]:
        """
        Get cache chat ID from settings.ini or return None.
        
        Returns:
            cache_chat_id if found in settings, None otherwise
        """
        settings_file = Path("settings.ini")
        if not settings_file.exists():
            return None
        
        try:
            config = configparser.ConfigParser()
            config.read(settings_file, encoding='utf-8')
            
            if 'bot' in config:
                cache_chat_id_str = config['bot'].get('cache_chat_id', '').strip()
                if cache_chat_id_str:
                    try:
                        return int(cache_chat_id_str)
                    except ValueError:
                        print(f"Warning: Invalid cache_chat_id in settings.ini: {cache_chat_id_str}")
                        return None
        except Exception as e:
            print(f"Warning: Could not read cache_chat_id from settings.ini: {e}")
        
        return None
    
    def set_cache_chat_id(self, chat_id: int) -> None:
        """
        Set cache chat ID and update ContentSender.
        
        Args:
            chat_id: Telegram chat ID to use for caching files
        """
        self.content_sender.cache_chat_id = chat_id
        if chat_id:
            print(f"File caching enabled with cache_chat_id: {chat_id}")
        else:
            print("File caching disabled")
    
    def get_scheduler(self) -> ContentScheduler:
        """
        Get scheduler instance for external configuration.
        
        Returns:
            ContentScheduler instance
        """
        return self.scheduler
    
    def update_user_chat_map(self, username: str, chat_id: int) -> None:
        """
        Update user_chat_map (called when users interact with bot).
        Also updates scheduler's user_chat_map if it's running.
        Saves chat_id to handler_list.Json for persistence.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
        """
        self.user_chat_map[username] = chat_id
        
        # Save chat_id to handler_list.Json
        self.user_manager.set_user_chat_id(username, chat_id)
        
        # Update scheduler's map if it has one
        if hasattr(self.scheduler, 'user_chat_map'):
            self.scheduler.user_chat_map[username] = chat_id


def main():
    """Main entry point."""
    try:
        bot = DailyContentBot()
        bot.start()
    except Exception as e:
        print(f"Error starting bot: {str(e)}")
        raise


if __name__ == "__main__":
    main()

