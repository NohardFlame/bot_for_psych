"""
Bot Settings GUI

Desktop application for managing bot settings, users, and bot control.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import configparser
import json
import threading
import webbrowser
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

# Handle imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.bot import DailyContentBot
from disk_api_handler.disk_handler import YandexDiskHandler, APIError


class BotSettingsGUI:
    """Main GUI application for bot settings management."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the GUI."""
        self.root = root
        self.root.title("Настройки бота")
        self.root.geometry("1000x750")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        
        # Setup modern styling
        self._setup_modern_style()
        
        # Center window on screen
        self._center_window()
        
        # Bot state
        self.bot_instance: Optional[DailyContentBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.bot_running = False
        
        # Settings file path
        self.settings_file = Path("settings.ini")
        self.handler_list_file = Path("handler_list.Json")
        
        # File monitoring for auto-refresh
        self.settings_file_mtime = 0
        self.handler_list_file_mtime = 0
        self.file_poll_running = False
        self.file_poll_thread = None
        self.user_editing = False  # Flag to pause polling during edits
        
        # Load handler list data
        self.handler_data: Dict[str, Any] = {}
        self._load_handler_list()
        self._update_file_mtimes()
        
        # Create UI
        self._create_ui()
        
        # Load settings on startup
        self._load_settings()
        
        # Start file polling
        self._start_file_polling()
        
        # Setup close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_modern_style(self):
        """Setup modern ttk styling with minimal design."""
        style = ttk.Style()
        
        # Try to use a modern theme
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
        
        # Configure colors - minimal modern palette
        style.configure('TFrame', background='#f5f5f5')
        style.configure('TLabelFrame', background='#f5f5f5', borderwidth=1, relief='solid')
        style.configure('TLabelFrame.Label', background='#f5f5f5', font=('Segoe UI', 9, 'bold'))
        
        # Modern button styling
        style.configure('TButton', 
                       padding=(12, 6),
                       font=('Segoe UI', 9),
                       borderwidth=1,
                       relief='flat')
        style.map('TButton',
                 background=[('active', '#e0e0e0'), ('!active', '#ffffff')],
                 relief=[('pressed', 'sunken'), ('!pressed', 'flat')])
        
        # Entry styling
        style.configure('TEntry',
                       padding=6,
                       font=('Segoe UI', 9),
                       borderwidth=1,
                       relief='solid',
                       fieldbackground='#ffffff')
        
        # Label styling
        style.configure('TLabel',
                       background='#f5f5f5',
                       font=('Segoe UI', 9),
                       foreground='#333333')
        
        # Treeview styling
        style.configure('Treeview',
                       background='#ffffff',
                       foreground='#333333',
                       fieldbackground='#ffffff',
                       font=('Segoe UI', 9),
                       rowheight=24)
        style.configure('Treeview.Heading',
                       background='#e8e8e8',
                       foreground='#333333',
                       font=('Segoe UI', 9, 'bold'),
                       relief='flat',
                       borderwidth=1)
        style.map('Treeview',
                 background=[('selected', '#4a9eff')],
                 foreground=[('selected', '#ffffff')])
        
        # Scrollbar styling
        style.configure('TScrollbar',
                       background='#e0e0e0',
                       troughcolor='#f5f5f5',
                       borderwidth=0,
                       arrowcolor='#666666',
                       darkcolor='#e0e0e0',
                       lightcolor='#e0e0e0')
    
    def _center_window(self):
        """Center the window on the screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
    
    def _create_ui(self):
        """Create the UI components."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # A. Settings Section (Top)
        self._create_settings_section(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=1, column=0, sticky=(tk.W, tk.E), pady=15
        )
        
        # B. Users Management Section (Middle)
        self._create_users_section(main_frame)
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=3, column=0, sticky=(tk.W, tk.E), pady=15
        )
        
        # C. Bot Control and Disk Link Section (Bottom)
        self._create_bottom_section(main_frame)
        
        # Configure row weights for responsive layout
        main_frame.rowconfigure(2, weight=1)  # Users section should expand
    
    def _create_settings_section(self, parent):
        """Create settings section."""
        settings_frame = ttk.LabelFrame(parent, text="Настройки токенов", padding="12")
        settings_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        settings_frame.columnconfigure(1, weight=1)
        
        # Bot token
        ttk.Label(settings_frame, text="Токен бота:").grid(
            row=0, column=0, sticky=tk.W, padx=8, pady=8
        )
        self.bot_token_var = tk.StringVar()
        bot_token_entry = ttk.Entry(
            settings_frame, textvariable=self.bot_token_var, show="*", width=50
        )
        bot_token_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=8, pady=8)
        
        # Disk token
        ttk.Label(settings_frame, text="Токен Яндекс.Диска:").grid(
            row=1, column=0, sticky=tk.W, padx=8, pady=8
        )
        self.disk_token_var = tk.StringVar()
        disk_token_entry = ttk.Entry(
            settings_frame, textvariable=self.disk_token_var, show="*", width=50
        )
        disk_token_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=8, pady=8)
        
        # Buttons
        buttons_frame = ttk.Frame(settings_frame)
        buttons_frame.grid(row=2, column=0, columnspan=2, pady=12)
        
        ttk.Button(
            buttons_frame, text="Загрузить", command=self._load_settings
        ).pack(side=tk.LEFT, padx=6)
        
        ttk.Button(
            buttons_frame, text="Сохранить", command=self._save_settings
        ).pack(side=tk.LEFT, padx=6)
    
    def _create_users_section(self, parent):
        """Create users management section with tree structure."""
        users_frame = ttk.LabelFrame(parent, text="Управление пользователями", padding="12")
        users_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        users_frame.columnconfigure(0, weight=1)
        users_frame.rowconfigure(1, weight=1)
        
        # Buttons frame
        buttons_frame = ttk.Frame(users_frame)
        buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=8)
        
        ttk.Button(
            buttons_frame, text="Загрузить программы с диска", command=self._load_programs_from_disk
        ).pack(side=tk.LEFT, padx=6)
        
        ttk.Button(
            buttons_frame, text="Сохранить изменения", command=self._save_users
        ).pack(side=tk.LEFT, padx=6)
        
        ttk.Button(
            buttons_frame, text="Обновить", command=self._manual_refresh
        ).pack(side=tk.LEFT, padx=6)
        
        # Treeview for programs and users
        tree_frame = ttk.Frame(users_frame)
        tree_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=8)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Create treeview with scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
        self.users_tree = ttk.Treeview(
            tree_frame,
            columns=("name", "begin_date"),
            show="tree headings",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.users_tree.yview)
        
        # Configure columns - changed from email to name
        self.users_tree.heading("#0", text="Программа / Пользователь")
        self.users_tree.heading("name", text="Имя")
        self.users_tree.heading("begin_date", text="Дата начала")
        self.users_tree.column("#0", width=280, minwidth=220)
        self.users_tree.column("name", width=220, minwidth=180)
        self.users_tree.column("begin_date", width=140, minwidth=120)
        
        # Pack treeview and scrollbar
        self.users_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Bind double-click to edit
        self.users_tree.bind("<Double-1>", self._on_tree_double_click)
        
        # Bind right-click for context menu
        self.users_tree.bind("<Button-3>", self._on_tree_right_click)
        
        # Create context menu
        self.context_menu = tk.Menu(self.root, tearoff=0, font=('Segoe UI', 9))
        self.context_menu.add_command(label="Удалить", command=self._delete_selected_item)
        
        # Store program items for reference
        self.program_items = {}  # program_key -> tree item id
        self.user_items = {}  # (program_key, username) -> tree item id
        self.selected_item = None
        
        self._refresh_users_tree()
    
    def _create_bottom_section(self, parent):
        """Create bottom section with bot control and disk link."""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)
        
        # Bot Control Section (Left)
        bot_frame = ttk.LabelFrame(bottom_frame, text="Управление ботом", padding="12")
        bot_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=8)
        
        self.start_bot_button = ttk.Button(
            bot_frame, text="Запустить бота", command=self._start_bot
        )
        self.start_bot_button.pack(pady=8)
        
        self.bot_status_label = ttk.Label(bot_frame, text="Статус: Остановлен")
        self.bot_status_label.pack(pady=6)
        
        # Delivery time control
        time_frame = ttk.Frame(bot_frame)
        time_frame.pack(pady=8, fill=tk.X)
        
        ttk.Label(time_frame, text="Время доставки:").pack(side=tk.LEFT, padx=6)
        
        self.delivery_time_var = tk.StringVar(value="09:00")
        time_entry = ttk.Entry(time_frame, textvariable=self.delivery_time_var, width=8)
        time_entry.pack(side=tk.LEFT, padx=6)
        ttk.Label(time_frame, text="(ЧЧ:ММ)").pack(side=tk.LEFT, padx=4)
        
        ttk.Button(
            time_frame, text="Обновить", command=self._update_delivery_time
        ).pack(side=tk.LEFT, padx=6)
        
        # Error indicator
        self.error_indicator_frame = ttk.Frame(bot_frame)
        self.error_indicator_frame.pack(pady=8, fill=tk.X)
        
        self.error_indicator_label = ttk.Label(
            self.error_indicator_frame,
            text="",
            foreground="red",
            cursor="hand2"
        )
        self.error_indicator_label.pack()
        self.error_indicator_label.bind("<Button-1>", self._on_error_indicator_click)
        
        # Store current errors
        self.current_errors = []
        self.error_poll_thread = None
        self.error_poll_running = False
        
        # Disk Link Section (Right)
        disk_frame = ttk.LabelFrame(bottom_frame, text="Яндекс.Диск", padding="12")
        disk_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=8)
        
        self.disk_link_button = ttk.Button(
            disk_frame, text="Открыть Яндекс.Диск", command=self._open_disk_link
        )
        self.disk_link_button.pack(pady=8)
        
        self.disk_status_label = ttk.Label(disk_frame, text="")
        self.disk_status_label.pack(pady=6)
    
    def _load_settings(self):
        """Load settings from settings.ini file."""
        if not self.settings_file.exists():
            return
        
        try:
            self.user_editing = True
            config = configparser.ConfigParser()
            config.read(self.settings_file, encoding='utf-8')
            
            if 'tokens' in config:
                self.bot_token_var.set(config['tokens'].get('bot_token', ''))
                self.disk_token_var.set(config['tokens'].get('disk_token', ''))
            
            # Load delivery time
            if 'scheduler' in config:
                delivery_time = config['scheduler'].get('delivery_time', '09:00')
                self.delivery_time_var.set(delivery_time)
            
            self._update_file_mtimes()
            self.user_editing = False
        except Exception as e:
            self.user_editing = False
            messagebox.showerror("Ошибка", f"Не удалось загрузить настройки: {str(e)}")
    
    def _save_settings(self):
        """Save settings to settings.ini file."""
        try:
            self.user_editing = True
            config = configparser.ConfigParser()
            if self.settings_file.exists():
                config.read(self.settings_file, encoding='utf-8')
            
            if 'tokens' not in config:
                config.add_section('tokens')
            
            config['tokens']['bot_token'] = self.bot_token_var.get()
            config['tokens']['disk_token'] = self.disk_token_var.get()
            
            # Save delivery time
            if 'scheduler' not in config:
                config.add_section('scheduler')
            
            config['scheduler']['delivery_time'] = self.delivery_time_var.get()
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                config.write(f)
            
            self._update_file_mtimes()
            self.user_editing = False
            messagebox.showinfo("Успех", "Настройки сохранены")
        except Exception as e:
            self.user_editing = False
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки: {str(e)}")
    
    def _load_handler_list(self):
        """Load handler_list.Json file."""
        if not self.handler_list_file.exists():
            self.handler_data = {}
            return
        
        try:
            with open(self.handler_list_file, 'r', encoding='utf-8') as f:
                self.handler_data = json.load(f)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить список пользователей: {str(e)}")
            self.handler_data = {}
    
    def _save_handler_list(self):
        """Save handler_list.Json file."""
        try:
            self.user_editing = True
            with open(self.handler_list_file, 'w', encoding='utf-8') as f:
                json.dump(self.handler_data, f, indent=4, ensure_ascii=False)
            self._update_file_mtimes()
            self.user_editing = False
            return True
        except Exception as e:
            self.user_editing = False
            messagebox.showerror("Ошибка", f"Не удалось сохранить список пользователей: {str(e)}")
            return False
    
    def _update_file_mtimes(self):
        """Update file modification time tracking."""
        try:
            if self.settings_file.exists():
                self.settings_file_mtime = os.path.getmtime(self.settings_file)
            if self.handler_list_file.exists():
                self.handler_list_file_mtime = os.path.getmtime(self.handler_list_file)
        except Exception:
            pass
    
    def _check_files_changed(self) -> bool:
        """Check if files have changed externally. Returns True if changed."""
        if self.user_editing:
            return False
        
        try:
            changed = False
            if self.settings_file.exists():
                current_mtime = os.path.getmtime(self.settings_file)
                if current_mtime != self.settings_file_mtime:
                    self.settings_file_mtime = current_mtime
                    changed = True
            
            if self.handler_list_file.exists():
                current_mtime = os.path.getmtime(self.handler_list_file)
                if current_mtime != self.handler_list_file_mtime:
                    self.handler_list_file_mtime = current_mtime
                    changed = True
            
            return changed
        except Exception:
            return False
    
    def _start_file_polling(self):
        """Start polling files for changes."""
        if self.file_poll_running:
            return
        
        self.file_poll_running = True
        
        def poll_files():
            while self.file_poll_running:
                try:
                    if self._check_files_changed():
                        # Update UI in main thread
                        self.root.after(0, self._auto_refresh_files)
                    time.sleep(3)  # Poll every 3 seconds
                except Exception as e:
                    print(f"File polling error: {str(e)}")
                    time.sleep(3)
        
        self.file_poll_thread = threading.Thread(target=poll_files, daemon=True)
        self.file_poll_thread.start()
    
    def _stop_file_polling(self):
        """Stop file polling."""
        self.file_poll_running = False
    
    def _auto_refresh_files(self):
        """Auto-refresh files when external changes detected."""
        if self.user_editing:
            return
        
        try:
            # Reload settings
            if self.settings_file.exists():
                config = configparser.ConfigParser()
                config.read(self.settings_file, encoding='utf-8')
                
                if 'tokens' in config:
                    self.bot_token_var.set(config['tokens'].get('bot_token', ''))
                    self.disk_token_var.set(config['tokens'].get('disk_token', ''))
                
                if 'scheduler' in config:
                    delivery_time = config['scheduler'].get('delivery_time', '09:00')
                    self.delivery_time_var.set(delivery_time)
            
            # Reload handler list
            self._load_handler_list()
            self._refresh_users_tree()
            
            # Show subtle notification (optional - can be removed if too intrusive)
            # Could add a status bar message here if desired
        except Exception as e:
            print(f"Auto-refresh error: {str(e)}")
    
    def _manual_refresh(self):
        """Manually refresh from files."""
        self._load_settings()
        self._load_handler_list()
        self._refresh_users_tree()
        messagebox.showinfo("Обновлено", "Данные обновлены из файлов")
    
    def _refresh_users_tree(self):
        """Refresh the users tree display."""
        # Clear existing items
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        self.program_items = {}
        self.user_items = {}
        
        if not self.handler_data:
            return
        
        for program_key, program_data in self.handler_data.items():
            begin_date = program_data.get('begin_date', '')
            
            # Create program item
            program_item = self.users_tree.insert(
                "",
                "end",
                text=f"📁 {program_key}",
                values=("", begin_date),
                tags=("program",)
            )
            self.program_items[program_key] = program_item
            
            # Add users under program
            for key, value in program_data.items():
                if key == 'begin_date' or not key.startswith('@'):
                    continue
                
                username = key
                # Handle both old format (string) and new format (dict)
                if isinstance(value, dict):
                    # Use 'name' field instead of 'email'
                    name = value.get('name', '') if value.get('name') else "(имя не указано)"
                    # chat_id is stored but not displayed in UI
                else:
                    # Old format - treat as name
                    name = value if value else "(имя не указано)"
                
                user_item = self.users_tree.insert(
                    program_item,
                    "end",
                    text=username,
                    values=(name, ""),
                    tags=("user",)
                )
                self.user_items[(program_key, username)] = user_item
            
            # Add "+" button item for adding users
            add_item = self.users_tree.insert(
                program_item,
                "end",
                text="➕ Добавить пользователя",
                values=("", ""),
                tags=("add_button",)
            )
        
        # Configure tags with modern styling
        self.users_tree.tag_configure("program", font=('Segoe UI', 10, 'bold'))
        self.users_tree.tag_configure("user", font=('Segoe UI', 9))
        self.users_tree.tag_configure("add_button", foreground="#0066cc", font=('Segoe UI', 9, 'italic'))
    
    def _load_programs_from_disk(self):
        """Load programs (folders) from Yandex Disk root."""
        disk_token = self.disk_token_var.get().strip()
        
        if not disk_token:
            messagebox.showerror("Ошибка", "Токен Яндекс.Диска не указан")
            return
        
        try:
            handler = YandexDiskHandler(token=disk_token)
            root_items = handler.list_directory("/")
            
            # Find all directories (programs)
            programs = []
            for item in root_items:
                if item.get('type') == 'dir':
                    folder_name = item.get('name', '')
                    # Skip system folders if needed
                    if folder_name and not folder_name.startswith('.'):
                        programs.append(folder_name)
            
            if not programs:
                messagebox.showinfo("Информация", "На диске не найдено папок программ")
                return
            
            # Initialize programs in handler_data if they don't exist
            new_programs = []
            for program in programs:
                if program not in self.handler_data:
                    self.handler_data[program] = {}
                    new_programs.append(program)
                # Ask for begin_date if not set (even for existing programs)
                if 'begin_date' not in self.handler_data[program] or not self.handler_data[program]['begin_date']:
                    begin_date = self._show_modal_dialog(
                        "Дата начала",
                        f"Введите дату начала для программы '{program}' (YYYY-MM-DD):\n"
                        "(Оставьте пустым, чтобы пропустить)",
                        initialvalue=""
                    )
                    if begin_date:
                        self.handler_data[program]['begin_date'] = begin_date
            
            self._refresh_users_tree()
            if new_programs:
                messagebox.showinfo("Успех", f"Добавлено {len(new_programs)} новых программ с диска")
            else:
                messagebox.showinfo("Информация", "Все программы уже загружены")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить программы с диска: {str(e)}")
    
    def _show_modal_dialog(self, title: str, prompt: str, initialvalue: str = "") -> Optional[str]:
        """Show a properly centered modal dialog."""
        dialog = simpledialog.askstring(title, prompt, initialvalue=initialvalue, parent=self.root)
        # Ensure dialog window is raised
        if hasattr(self.root, 'focus_force'):
            self.root.focus_force()
        return dialog
    
    def _on_tree_double_click(self, event):
        """Handle double-click on tree items."""
        item = self.users_tree.selection()[0] if self.users_tree.selection() else None
        if not item:
            return
        
        tags = self.users_tree.item(item, "tags")
        if "add_button" in tags:
            # Add user to this program
            parent = self.users_tree.parent(item)
            if parent:
                program_text = self.users_tree.item(parent, "text")
                # Extract program name (remove folder icon)
                program_key = program_text.replace("📁 ", "").strip()
                self._add_user_to_program(program_key)
        elif "user" in tags:
            # Edit user name
            self._edit_user_name(item)
        elif "program" in tags:
            # Edit program begin_date
            self._edit_program_date(item)
    
    def _add_user_to_program(self, program_key: str):
        """Add a user to a specific program with inline input."""
        if program_key not in self.handler_data:
            self.handler_data[program_key] = {}
        
        # Create a popup window for username input
        popup = tk.Toplevel(self.root)
        popup.title("Добавить пользователя")
        popup.geometry("420x180")
        popup.transient(self.root)
        popup.grab_set()
        popup.resizable(False, False)
        
        # Center popup properly
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (popup.winfo_width() // 2)
        y = (popup.winfo_screenheight() // 2) - (popup.winfo_height() // 2)
        popup.geometry(f"+{x}+{y}")
        popup.lift()
        popup.focus_force()
        
        # Main frame
        main_frame = ttk.Frame(popup, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text=f"Программа: {program_key}", font=('Segoe UI', 10, 'bold')).pack(pady=8)
        
        ttk.Label(main_frame, text="Username (начинается с @):").pack(pady=4)
        username_var = tk.StringVar()
        username_entry = ttk.Entry(main_frame, textvariable=username_var, width=35)
        username_entry.pack(pady=4)
        username_entry.focus()
        username_entry.bind('<Return>', lambda e: self._process_add_user(popup, program_key, username_var, name_var))
        username_entry.bind('<Control-v>', lambda e: username_entry.event_generate('<<Paste>>'))
        
        ttk.Label(main_frame, text="Имя (необязательно):").pack(pady=4)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=name_var, width=35)
        name_entry.pack(pady=4)
        name_entry.bind('<Control-v>', lambda e: name_entry.event_generate('<<Paste>>'))
        
        def add_user():
            self._process_add_user(popup, program_key, username_var, name_var)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Добавить", command=add_user).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=popup.destroy).pack(side=tk.LEFT, padx=5)
        
        popup.bind('<Return>', lambda e: add_user())
        popup.bind('<Escape>', lambda e: popup.destroy())
    
    def _process_add_user(self, popup, program_key: str, username_var: tk.StringVar, name_var: tk.StringVar = None):
        """Process adding a user."""
        username = username_var.get().strip()
        if not username:
            messagebox.showerror("Ошибка", "Username не может быть пустым")
            return
        
        if not username.startswith('@'):
            username = '@' + username
        
        # Check if user already exists
        for prog_key, prog_data in self.handler_data.items():
            if username in prog_data:
                messagebox.showwarning(
                    "Предупреждение",
                    f"Пользователь {username} уже существует в программе {prog_key}"
                )
                return
        
        name = ""
        if name_var:
            name = name_var.get().strip()
        
        # Add user in new format (dict with name and chat_id)
        self.handler_data[program_key][username] = {
            'name': name,
            'chat_id': None,
            'last_message_date': None
        }
        popup.destroy()
        self._refresh_users_tree()
    
    def _edit_user_name(self, item):
        """Edit user name inline."""
        username = self.users_tree.item(item, "text")
        parent = self.users_tree.parent(item)
        program_text = self.users_tree.item(parent, "text")
        program_key = program_text.replace("📁 ", "").strip()
        
        # Get current name (handle both old and new format)
        user_data = self.handler_data[program_key].get(username, "")
        if isinstance(user_data, dict):
            current_name = user_data.get('name', '')
            current_chat_id = user_data.get('chat_id')
            current_last_message_date = user_data.get('last_message_date')
        else:
            # Old format
            current_name = user_data if user_data else ''
            current_chat_id = None
            current_last_message_date = None
        
        new_name = self._show_modal_dialog(
            "Изменить имя",
            f"Пользователь: {username}\nВведите новое имя или оставьте пустым:",
            initialvalue=current_name
        )
        
        if new_name is not None:
            # Save in new format
            self.handler_data[program_key][username] = {
                'name': new_name if new_name else '',
                'chat_id': current_chat_id,
                'last_message_date': current_last_message_date
            }
            self._refresh_users_tree()
    
    def _edit_program_date(self, item):
        """Edit program begin_date."""
        program_text = self.users_tree.item(item, "text")
        program_key = program_text.replace("📁 ", "").strip()
        
        current_date = self.handler_data[program_key].get('begin_date', '')
        
        new_date = self._show_modal_dialog(
            "Изменить дату начала",
            f"Программа: {program_key}\nВведите дату начала (YYYY-MM-DD):",
            initialvalue=current_date
        )
        
        if new_date is not None:
            self.handler_data[program_key]['begin_date'] = new_date
            self._refresh_users_tree()
    
    def _on_tree_right_click(self, event):
        """Handle right-click on tree items."""
        item = self.users_tree.identify_row(event.y)
        if item:
            self.users_tree.selection_set(item)
            self.selected_item = item
            
            tags = self.users_tree.item(item, "tags")
            if "user" in tags or "program" in tags:
                # Show context menu for users and programs
                self.context_menu.post(event.x_root, event.y_root)
    
    def _delete_selected_item(self):
        """Delete the selected item from tree."""
        if not self.selected_item:
            return
        
        item = self.selected_item
        tags = self.users_tree.item(item, "tags")
        
        if "user" in tags:
            username = self.users_tree.item(item, "text")
            parent = self.users_tree.parent(item)
            program_text = self.users_tree.item(parent, "text")
            program_key = program_text.replace("📁 ", "").strip()
            
            self._remove_user(program_key, username)
        elif "program" in tags:
            program_text = self.users_tree.item(item, "text")
            program_key = program_text.replace("📁 ", "").strip()
            self._delete_program(program_key)
        
        self.selected_item = None
    
    def _remove_user(self, program_key: str, username: str):
        """Remove a user from a program."""
        if program_key not in self.handler_data:
            return
        
        if username not in self.handler_data[program_key]:
            return
        
        # Confirm deletion
        if messagebox.askyesno(
            "Подтверждение",
            f"Удалить пользователя {username} из программы {program_key}?"
        ):
            del self.handler_data[program_key][username]
            self._refresh_users_tree()
    
    def _delete_program(self, program_key: str):
        """Delete a program and all its users."""
        if program_key not in self.handler_data:
            return
        
        # Get all users in the program
        users_in_program = []
        for key, value in self.handler_data[program_key].items():
            if key.startswith('@'):
                users_in_program.append(key)
        
        # Build confirmation message
        if users_in_program:
            user_list = '\n'.join(f"  - {user}" for user in users_in_program)
            message = (
                f"Удалить программу '{program_key}'?\n\n"
                f"Это также удалит всех пользователей в программе ({len(users_in_program)}):\n"
                f"{user_list}\n\n"
                "Вы уверены?"
            )
        else:
            message = f"Удалить программу '{program_key}'?\n\n(В программе нет пользователей)"
        
        # Confirm deletion
        if messagebox.askyesno("Подтверждение удаления программы", message):
            del self.handler_data[program_key]
            self._refresh_users_tree()
    
    def _save_users(self):
        """Save users to handler_list.Json."""
        if self._save_handler_list():
            messagebox.showinfo("Успех", "Изменения сохранены")
    
    def _start_bot(self):
        """Start the bot in a separate thread."""
        if self.bot_running:
            return
        
        # Validate tokens
        bot_token = self.bot_token_var.get().strip()
        disk_token = self.disk_token_var.get().strip()
        
        if not bot_token:
            messagebox.showerror("Ошибка", "Токен бота не указан")
            return
        
        if not disk_token:
            messagebox.showerror("Ошибка", "Токен Яндекс.Диска не указан")
            return
        
        try:
            # Get delivery time from settings
            delivery_time_str = self.delivery_time_var.get().strip()
            from datetime import time as dt_time
            try:
                parts = delivery_time_str.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                hour = int(parts[0])
                minute = int(parts[1])
                if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                    raise ValueError("Invalid time range")
                initial_delivery_time = dt_time(hour, minute)
            except (ValueError, IndexError):
                messagebox.showerror("Ошибка", "Неверный формат времени доставки. Используйте ЧЧ:ММ")
                return
            
            # Create bot instance
            self.bot_instance = DailyContentBot(
                bot_token=bot_token,
                disk_token=disk_token
            )
            
            # Set delivery time from settings before starting
            scheduler = self.bot_instance.get_scheduler()
            scheduler.set_delivery_time(initial_delivery_time, {})
            
            # Update UI with actual time
            current_time = scheduler.get_delivery_time()
            self.delivery_time_var.set(f"{current_time.hour:02d}:{current_time.minute:02d}")
            
            # Start bot in separate thread
            def run_bot():
                try:
                    self.bot_instance.start()
                except Exception as e:
                    print(f"Bot error: {str(e)}")
                    self.bot_running = False
                    self.root.after(0, lambda: self._update_bot_status(False))
            
            self.bot_thread = threading.Thread(target=run_bot, daemon=False)
            self.bot_thread.start()
            
            self.bot_running = True
            self._update_bot_status(True)
            
            # Start error polling
            self._start_error_polling()
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось запустить бота: {str(e)}")
            self.bot_running = False
            self._update_bot_status(False)
    
    def _update_bot_status(self, running: bool):
        """Update bot status display."""
        self.bot_running = running
        if running:
            self.start_bot_button.config(text="Бот запущен", state='disabled')
            self.bot_status_label.config(text="Статус: Запущен", foreground="green")
        else:
            self.start_bot_button.config(text="Запустить бота", state='normal')
            self.bot_status_label.config(text="Статус: Остановлен", foreground="black")
            # Stop error polling when bot stops
            self._stop_error_polling()
    
    def _update_delivery_time(self):
        """Update delivery time in scheduler and save to settings."""
        time_str = self.delivery_time_var.get().strip()
        
        # Validate time format
        try:
            from datetime import time as dt_time
            parts = time_str.split(':')
            if len(parts) != 2:
                raise ValueError("Invalid format")
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("Invalid time range")
            delivery_time = dt_time(hour, minute)
        except (ValueError, IndexError):
            messagebox.showerror("Ошибка", "Неверный формат времени. Используйте ЧЧ:ММ (например, 09:00)")
            return
        
        # Update scheduler if bot is running
        if self.bot_running and self.bot_instance:
            try:
                scheduler = self.bot_instance.get_scheduler()
                # Pass the actual user_chat_map, or None to use existing one
                user_map = getattr(self.bot_instance, 'user_chat_map', None)
                scheduler.set_delivery_time(delivery_time, user_map)
                messagebox.showinfo("Успех", f"Время доставки обновлено: {time_str}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось обновить время доставки: {str(e)}")
        else:
            messagebox.showinfo("Информация", f"Время доставки будет установлено при запуске бота: {time_str}")
        
        # Always save to settings file
        try:
            config = configparser.ConfigParser()
            if self.settings_file.exists():
                config.read(self.settings_file, encoding='utf-8')
            
            if 'scheduler' not in config:
                config.add_section('scheduler')
            
            config['scheduler']['delivery_time'] = time_str
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                config.write(f)
        except Exception as e:
            print(f"Warning: Could not save delivery time to settings: {str(e)}")
    
    def _start_error_polling(self):
        """Start polling scheduler for errors."""
        if self.error_poll_running:
            return
        
        self.error_poll_running = True
        
        def poll_errors():
            import time
            while self.error_poll_running and self.bot_running:
                try:
                    if self.bot_instance:
                        scheduler = self.bot_instance.get_scheduler()
                        errors = scheduler.get_delivery_errors()
                        
                        # Update UI in main thread
                        self.root.after(0, lambda: self._update_error_indicator(errors))
                    
                    # Poll every 15 seconds (between 10-20 as requested)
                    time.sleep(15)
                except Exception as e:
                    print(f"Error polling: {str(e)}")
                    time.sleep(15)
        
        self.error_poll_thread = threading.Thread(target=poll_errors, daemon=True)
        self.error_poll_thread.start()
    
    def _stop_error_polling(self):
        """Stop error polling."""
        self.error_poll_running = False
        self.current_errors = []
        self._update_error_indicator([])
    
    def _update_error_indicator(self, errors: List[Dict[str, Any]]):
        """Update error indicator display."""
        self.current_errors = errors
        
        if not errors:
            self.error_indicator_label.config(text="")
            return
        
        # Get unique usernames with errors
        unique_users = set(err['username'] for err in errors)
        error_count = len(unique_users)
        
        if error_count == 1:
            text = f"⚠️ Ошибка доставки для 1 пользователя (нажмите для повтора)"
        else:
            text = f"⚠️ Ошибки доставки для {error_count} пользователей (нажмите для повтора)"
        
        self.error_indicator_label.config(text=text)
    
    def _on_error_indicator_click(self, event):
        """Handle click on error indicator to retry delivery."""
        if not self.current_errors:
            return
        
        if not self.bot_running or not self.bot_instance:
            messagebox.showwarning("Предупреждение", "Бот не запущен")
            return
        
        # Get unique usernames with errors
        usernames = list(set(err['username'] for err in self.current_errors))
        
        # Confirm retry
        if not messagebox.askyesno(
            "Повторная доставка",
            f"Повторить доставку для {len(usernames)} пользователя(ей)?\n\n"
            f"Пользователи: {', '.join(usernames)}"
        ):
            return
        
        # Show progress
        self.error_indicator_label.config(text="⏳ Выполняется доставка...", foreground="blue")
        self.root.update()
        
        def retry_delivery():
            try:
                scheduler = self.bot_instance.get_scheduler()
                results = scheduler.force_delivery_to_users(usernames)
                
                # Update UI in main thread
                def update_ui():
                    successful = results['successful']
                    failed = results['failed']
                    
                    if failed == 0:
                        # All successful, clear errors
                        scheduler.clear_delivery_errors()
                        self.current_errors = []
                        self._update_error_indicator([])
                        messagebox.showinfo(
                            "Успех",
                            f"Доставка успешно выполнена для всех {successful} пользователя(ей)"
                        )
                    else:
                        # Some failed, update indicator
                        new_errors = scheduler.get_delivery_errors()
                        self._update_error_indicator(new_errors)
                        messagebox.showwarning(
                            "Частичный успех",
                            f"Успешно: {successful}, Ошибок: {failed}\n"
                            f"Проверьте индикатор ошибок для деталей"
                        )
                
                self.root.after(0, update_ui)
            except Exception as e:
                def show_error():
                    messagebox.showerror("Ошибка", f"Не удалось выполнить доставку: {str(e)}")
                    # Refresh error list
                    if self.bot_instance:
                        scheduler = self.bot_instance.get_scheduler()
                        errors = scheduler.get_delivery_errors()
                        self._update_error_indicator(errors)
                
                self.root.after(0, show_error)
        
        # Run retry in separate thread to avoid blocking UI
        threading.Thread(target=retry_delivery, daemon=True).start()
    
    def _stop_bot(self):
        """Stop the bot."""
        if not self.bot_running or not self.bot_instance:
            return
        
        try:
            # Stop error polling first
            self._stop_error_polling()
            
            # Use the bot's stop method
            self.bot_instance.stop()
            self.bot_running = False
            self._update_bot_status(False)
        except Exception as e:
            print(f"Error stopping bot: {str(e)}")
            self.bot_running = False
            self._update_bot_status(False)
    
    def _open_disk_link(self):
        """Open Yandex Disk root folder link."""
        disk_token = self.disk_token_var.get().strip()
        
        if not disk_token:
            messagebox.showerror("Ошибка", "Токен Яндекс.Диска не указан")
            return
        
        self.disk_status_label.config(text="Загрузка...", foreground="blue")
        self.disk_link_button.config(state='disabled')
        
        def fetch_link():
            try:
                handler = YandexDiskHandler(token=disk_token)
                link = handler.get_root_folder_link()
                
                if link:
                    self.root.after(0, lambda: webbrowser.open(link))
                    self.root.after(0, lambda: self.disk_status_label.config(
                        text="Ссылка открыта", foreground="green"
                    ))
                else:
                    self.root.after(0, lambda: self.disk_status_label.config(
                        text="Не удалось получить ссылку", foreground="red"
                    ))
            except Exception as e:
                self.root.after(0, lambda: self.disk_status_label.config(
                    text=f"Ошибка: {str(e)}", foreground="red"
                ))
            finally:
                self.root.after(0, lambda: self.disk_link_button.config(state='normal'))
        
        threading.Thread(target=fetch_link, daemon=True).start()
    
    def _on_closing(self):
        """Handle window closing event."""
        if self.bot_running:
            if messagebox.askyesno(
                "Подтверждение",
                "Если закрыть программу сейчас, то бот перестанет работать, Вы уверены?"
            ):
                # Stop file polling
                self._stop_file_polling()
                # Stop error polling
                self._stop_error_polling()
                self._stop_bot()
                self.root.destroy()
        else:
            # Stop file polling
            self._stop_file_polling()
            # Stop error polling if it's running
            self._stop_error_polling()
            self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = BotSettingsGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
