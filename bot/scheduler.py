"""
Scheduler Module

Schedules automatic content delivery
"""

import threading
import time
from datetime import datetime, time as dt_time
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
import telebot

# Handle both package and direct execution
try:
    from .user_manager import UserManager
    from .day_calculator import DayCalculator
    from .content_fetcher import ContentFetcher
    from .content_sender import ContentSender
    from .file_id_cache import FileIdCache
except ImportError:
    from user_manager import UserManager
    from day_calculator import DayCalculator
    from content_fetcher import ContentFetcher
    from content_sender import ContentSender
    from file_id_cache import FileIdCache

from disk_api_handler.disk_handler import YandexDiskHandler


@dataclass
class DeliveryError:
    """Represents a delivery error for a user."""
    username: str
    chat_id: int
    error_message: str
    timestamp: datetime


class ContentScheduler:
    """Schedules automatic daily content delivery."""
    
    def __init__(
        self,
        bot: telebot.TeleBot,
        user_manager: UserManager,
        disk_handler: YandexDiskHandler,
        delivery_time: dt_time = dt_time(9, 0),  # Default: 9:00 AM
        file_id_cache: Optional[FileIdCache] = None,
        cache_chat_id: Optional[int] = None
    ):
        """
        Initialize ContentScheduler.
        
        Args:
            bot: TeleBot instance
            user_manager: UserManager instance
            disk_handler: YandexDiskHandler instance
            delivery_time: Time of day to deliver content (default: 9:00 AM)
            file_id_cache: Optional FileIdCache instance for caching file_ids
            cache_chat_id: Optional chat ID where files are uploaded for caching
        """
        self.bot = bot
        self.user_manager = user_manager
        self.disk_handler = disk_handler
        self.delivery_time = delivery_time
        self.running = False
        self.thread = None
        
        # Track delivery errors for UI notification
        self.delivery_errors: List[DeliveryError] = []
        self.errors_lock = threading.Lock()  # Thread-safe access to errors
        
        # Track last delivery date to avoid duplicate deliveries
        self.last_delivery_date: Optional[datetime.date] = None
        self.delivery_lock = threading.Lock()  # Lock to prevent concurrent deliveries
        
        # Initialize content modules
        self.content_fetcher = ContentFetcher(disk_handler)
        self.content_sender = ContentSender(
            bot,
            disk_handler,
            file_id_cache=file_id_cache,
            cache_chat_id=cache_chat_id
        )
        self.day_calculator = DayCalculator()
    
    def _deliver_content_to_user(self, username: str, chat_id: int) -> Tuple[bool, Optional[str]]:
        """
        Deliver content to a specific user.
        Checks last_message_date and delivers all missing days.
        Updates timestamp immediately after each successful day delivery.
        
        Args:
            username: Telegram username
            chat_id: Telegram chat ID
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            success is True if at least one day was delivered successfully
        """
        try:
            # Check if user is registered
            if not self.user_manager.is_user_registered(username):
                return False, f"User {username} is not registered"
            
            # Get program data
            program_data = self.user_manager.get_program_data(username)
            if not program_data:
                return False, f"Program data not found for {username}"
            
            program_key = self.user_manager.find_user_program(username)
            begin_date = program_data.get('begin_date')
            
            if not begin_date:
                return False, f"Begin date not found for {username}"
            
            # Get user's last_message_date
            last_message_date = self.user_manager.get_user_last_message_date(username)
            
            # Calculate which days need to be delivered based on dates
            days_to_deliver = self.day_calculator.calculate_days_to_deliver(
                begin_date,
                last_message_date
            )
            
            # If date-based calculation returns empty, check for backlog (available days on disk)
            if not days_to_deliver:
                # Calculate max day to check (use a reasonable upper limit or current day)
                from datetime import date as dt_date, datetime
                begin_date_obj = self.day_calculator.parse_begin_date(begin_date)
                if begin_date_obj:
                    current_date = dt_date.today()
                    current_day = (current_date - begin_date_obj).days + 1
                    if current_day < 1:
                        current_day = 100  # Check up to day 100 if program hasn't started
                    max_day = max(current_day, 100)  # At least check up to day 100 for backlog
                else:
                    max_day = 100  # Default to checking up to day 100
                
                # Get available days from disk
                available_days = self.content_fetcher.get_available_days(program_key, max_day)
                
                # Filter out days that have already been delivered
                if last_message_date is not None and begin_date_obj:
                    try:
                        from datetime import datetime
                        last_date = datetime.fromtimestamp(last_message_date).date()
                        last_day = (last_date - begin_date_obj).days + 1
                        # Only deliver days after the last delivered day
                        days_to_deliver = [d for d in available_days if d > last_day]
                    except (ValueError, OSError):
                        # Invalid timestamp, deliver all available days
                        days_to_deliver = available_days
                else:
                    # No last_message_date or begin_date, deliver all available days
                    days_to_deliver = available_days
            
            if not days_to_deliver:
                # User is up to date, nothing to deliver
                return True, None
            
            # Deliver each day in sequence
            at_least_one_success = False
            last_error = None
            has_non_missing_folder_errors = False  # Track if we encountered errors other than missing folders
            
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
                            # Day not ready yet, silently skip it (don't update timestamp, don't log as error)
                            continue
                        else:
                            # Other error, skip this day
                            has_non_missing_folder_errors = True
                            last_error = f"Content fetch error for day {day_number} ({username}): {error_msg}"
                            continue
                    
                    # Send content
                    success = self.content_sender.send_day_content(chat_id, content_data)
                    if not success:
                        # Failed to send, don't update timestamp
                        has_non_missing_folder_errors = True
                        last_error = f"Failed to send content for day {day_number} to {username}"
                        continue
                    
                    # Success! Update last_message_date immediately
                    self.user_manager.update_user_last_message_date(username, day_number, begin_date)
                    at_least_one_success = True
                    
                except Exception as e:
                    # Error delivering this day, continue with next day
                    has_non_missing_folder_errors = True
                    last_error = f"Exception delivering day {day_number} to {username}: {str(e)}"
                    print(last_error)
                    continue
            
            # Return success if at least one day was delivered
            if at_least_one_success:
                return True, None
            elif not has_non_missing_folder_errors:
                # All days failed only because folders don't exist - silently skip
                return True, None
            else:
                # All days failed for other reasons
                return False, last_error or f"Failed to deliver any days to {username}"
            
        except Exception as e:
            error_msg = f"Exception delivering to {username}: {str(e)}"
            print(error_msg)
            return False, error_msg
    
    def schedule_delivery(self, user_chat_map: dict) -> Dict[str, Any]:
        """
        Schedule content delivery for all users.
        Errors for individual users don't stop delivery to others.
        
        Args:
            user_chat_map: Dictionary mapping username to chat_id
        
        Returns:
            Dictionary with delivery statistics:
            - total_users: int
            - successful: int
            - failed: int
            - errors: List[DeliveryError]
        """
        results = {
            'total_users': len(user_chat_map),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        current_errors = []
        
        for username, chat_id in user_chat_map.items():
            success, error_msg = self._deliver_content_to_user(username, chat_id)
            
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1
                # Record error
                error = DeliveryError(
                    username=username,
                    chat_id=chat_id,
                    error_message=error_msg or "Unknown error",
                    timestamp=datetime.now()
                )
                current_errors.append(error)
        
        # Store errors thread-safely
        if current_errors:
            with self.errors_lock:
                self.delivery_errors.extend(current_errors)
                # Keep only last 100 errors to prevent memory issues
                if len(self.delivery_errors) > 100:
                    self.delivery_errors = self.delivery_errors[-100:]
        
        results['errors'] = current_errors
        return results
    
    def _is_delivery_time(self) -> bool:
        """
        Check if current time has passed delivery time today and we haven't delivered yet.
        
        Returns:
            True if it's time to deliver, False otherwise
        """
        now = datetime.now()
        today = now.date()
        
        # Check if we already delivered today
        if self.last_delivery_date == today:
            return False
        
        # Create delivery datetime for today
        delivery_datetime = datetime.combine(today, self.delivery_time)
        
        # If current time has passed delivery time today, it's time to deliver
        result = now >= delivery_datetime
        
        return result
    
    def start(self, user_chat_map: dict) -> None:
        """
        Start the scheduler.
        
        Args:
            user_chat_map: Dictionary mapping username to chat_id
        """
        if self.running:
            return
        
        self.user_chat_map = user_chat_map
        self.running = True
        
        def run_scheduler():
            # Wait a bit to let immediate_check run first if needed
            time.sleep(5)
            
            while self.running:
                try:
                    # Check if it's delivery time (but don't check immediately - let immediate_check handle that)
                    if self._is_delivery_time() and hasattr(self, 'user_chat_map') and self.user_chat_map:
                        with self.delivery_lock:
                            # Double-check after acquiring lock (another thread might have delivered)
                            if self._is_delivery_time() and hasattr(self, 'user_chat_map') and self.user_chat_map:
                                print(f"Scheduler: Starting delivery at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                results = self.schedule_delivery(self.user_chat_map)
                                self.last_delivery_date = datetime.now().date()
                                
                                print(f"Scheduler: Delivery completed. Successful: {results['successful']}, Failed: {results['failed']}")
                                
                                if results['failed'] > 0:
                                    print(f"Scheduler: {len(results['errors'])} users had errors")
                                    for error in results['errors']:
                                        print(f"  - {error.username}: {error.error_message}")
                    
                    # Sleep for 1 minute before checking again
                    time.sleep(60)  # 1 minute
                    
                except Exception as e:
                    print(f"Scheduler error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(3600)  # Wait 1 hour on error
        
        # Check immediately on start if it's already past delivery time
        def immediate_check():
            # Small delay to ensure user_chat_map is set
            time.sleep(2)
            
            if not self.running:
                return
            
            if hasattr(self, 'user_chat_map') and self.user_chat_map:
                if self._is_delivery_time():
                    with self.delivery_lock:
                        # Double-check after acquiring lock (another thread might have delivered)
                        if self._is_delivery_time() and hasattr(self, 'user_chat_map') and self.user_chat_map:
                            print(f"Scheduler: Immediate check - starting delivery at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            print(f"Scheduler: Delivering to {len(self.user_chat_map)} users")
                            results = self.schedule_delivery(self.user_chat_map)
                            self.last_delivery_date = datetime.now().date()
                            print(f"Scheduler: Immediate delivery completed. Successful: {results['successful']}, Failed: {results['failed']}")
                            if results['failed'] > 0:
                                for error in results['errors']:
                                    print(f"  - {error.username}: {error.error_message}")
            elif not self.user_chat_map:
                print("Scheduler: No users with chat_ids found. Users need to interact with bot first to populate chat_ids.")
        
        # Run immediate check in separate thread
        threading.Thread(target=immediate_check, daemon=True).start()
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def is_running(self) -> bool:
        """
        Check if scheduler is running.
        
        Returns:
            True if scheduler is running, False otherwise
        """
        return self.running
    
    def get_delivery_time(self) -> dt_time:
        """
        Get current delivery time.
        
        Returns:
            Current delivery time
        """
        return self.delivery_time
    
    def set_delivery_time(self, delivery_time: dt_time, user_chat_map: dict = None) -> None:
        """
        Set delivery time. If scheduler is running, it will restart with new time.
        
        Args:
            delivery_time: New delivery time
            user_chat_map: Optional user_chat_map to use when restarting.
                          If not provided and scheduler is running, uses existing map.
        """
        was_running = self.running
        old_time = self.delivery_time
        self.delivery_time = delivery_time
        
        # Reset last delivery date when time changes (only if time actually changed)
        # This allows immediate delivery if new time has already passed today
        if old_time != delivery_time:
            self.last_delivery_date = None
        
        # If scheduler was running, restart it with new time
        if was_running:
            self.stop()
            # Small delay to ensure stop completes
            time.sleep(0.5)
            # Use provided map or existing one
            chat_map = user_chat_map if user_chat_map is not None else getattr(self, 'user_chat_map', {})
            self.start(chat_map)
            
            # Also trigger immediate check for time change
            def check_immediately():
                time.sleep(2)  # Small delay for scheduler to restart
                if not self.running:
                    return
                if not hasattr(self, 'user_chat_map') or not self.user_chat_map:
                    return
                if self._is_delivery_time():
                    print(f"Scheduler: Time changed - immediate delivery at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    results = self.schedule_delivery(self.user_chat_map)
                    self.last_delivery_date = datetime.now().date()
                    print(f"Scheduler: Delivery completed. Successful: {results['successful']}, Failed: {results['failed']}")
                    if results['failed'] > 0:
                        for error in results['errors']:
                            print(f"  - {error.username}: {error.error_message}")
            
            threading.Thread(target=check_immediately, daemon=True).start()
        else:
            # Even if not running, check if we should deliver immediately when it starts
            # This is handled by immediate_check() in start()
            pass
    
    def get_delivery_errors(self, clear: bool = False) -> List[Dict[str, Any]]:
        """
        Get list of delivery errors for UI notification.
        
        Args:
            clear: If True, clears the error list after returning
        
        Returns:
            List of error dictionaries with keys: username, chat_id, error_message, timestamp
        """
        with self.errors_lock:
            errors = [
                {
                    'username': err.username,
                    'chat_id': err.chat_id,
                    'error_message': err.error_message,
                    'timestamp': err.timestamp.isoformat()
                }
                for err in self.delivery_errors
            ]
            
            if clear:
                self.delivery_errors.clear()
            
            return errors
    
    def force_delivery_to_users(self, usernames: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Force delivery to specific users (for retrying failed deliveries).
        
        Args:
            usernames: List of usernames to deliver to. If None, delivers to all users in user_chat_map
        
        Returns:
            Dictionary with delivery statistics (same format as schedule_delivery)
        """
        if not hasattr(self, 'user_chat_map'):
            return {'total_users': 0, 'successful': 0, 'failed': 0, 'errors': []}
        
        if usernames is None:
            # Deliver to all users
            user_map = self.user_chat_map
        else:
            # Deliver only to specified users
            user_map = {
                username: chat_id
                for username, chat_id in self.user_chat_map.items()
                if username in usernames
            }
        
        print(f"Forcing delivery to {len(user_map)} user(s)")
        results = self.schedule_delivery(user_map)
        return results
    
    def clear_delivery_errors(self) -> None:
        """Clear all stored delivery errors."""
        with self.errors_lock:
            self.delivery_errors.clear()

