"""
Twitch Chat Tools

Main chat monitoring and interaction tool for Twitch streams. Connects to
Twitch IRC, displays chat messages in a log window, and provides basic
chat interaction capabilities including custom commands and auto messages.
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext
import json
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
import asyncio
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from logger_setup import setup_logger
from chat_tools_modules import TwitchChatBot, CommandHandler, AutoMessageHandler
from chat_tools_modules.token_manager import TokenManager

logger = setup_logger(__name__)


class ChatTools:
    """Main chat tools application with Twitch integration."""
    
    def __init__(self) -> None:
        """Initialise the chat tools application."""
        self.root = tk.Tk()
        self.root.title("Chat Tools")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        self.config_path = Path(__file__).parent / "config" / "chat_tools_config.json"
        self.config: Optional[dict] = None
        self.is_connected: bool = False
        
        # Bot instance
        self.bot: Optional[TwitchChatBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Command and auto-message handlers
        self.command_handler: Optional[CommandHandler] = None
        self.auto_msg_handler: Optional[AutoMessageHandler] = None
        
        # Chat activity tracking
        self.chat_activity_timestamps: list[float] = []
        
        # File watcher for config changes
        self.config_observer: Optional[Observer] = None
        
        self._create_ui()
        self._load_config()
        self._start_config_watcher()
    
    def _create_ui(self) -> None:
        """Create the chat tools UI components."""
        # Title bar with connection status
        header_frame = tk.Frame(self.root, bg="#2C3E50", pady=10)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            header_frame,
            text="Twitch Chat Tools",
            font=("Arial", 16, "bold"),
            bg="#2C3E50",
            fg="white"
        )
        title_label.pack(side=tk.LEFT, padx=20)
        
        self.status_label = tk.Label(
            header_frame,
            text="● Disconnected",
            font=("Arial", 11),
            bg="#2C3E50",
            fg="#E74C3C"
        )
        self.status_label.pack(side=tk.RIGHT, padx=20)
        
        # Log display area
        log_frame = tk.Frame(self.root, padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(
            log_frame,
            text="Chat Log:",
            font=("Arial", 11, "bold")
        ).pack(anchor="w")
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            bg="#F8F9FA",
            fg="#2C3E50"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Control buttons
        control_frame = tk.Frame(self.root, pady=10)
        control_frame.pack(fill=tk.X)
        
        self.connect_btn = tk.Button(
            control_frame,
            text="Connect",
            command=self.toggle_connection,
            width=15,
            font=("Arial", 10, "bold"),
            bg="#4CAF50",
            fg="white"
        )
        self.connect_btn.pack(side=tk.LEFT, padx=10)
        
        clear_btn = tk.Button(
            control_frame,
            text="Clear Log",
            command=self.clear_log,
            width=15,
            font=("Arial", 10)
        )
        clear_btn.pack(side=tk.LEFT, padx=10)
        
        settings_btn = tk.Button(
            control_frame,
            text="Open Settings",
            command=self.open_settings,
            width=15,
            font=("Arial", 10)
        )
        settings_btn.pack(side=tk.LEFT, padx=10)
    
    def _load_config(self) -> None:
        """Load Twitch configuration from file."""
        if not self.config_path.exists():
            self.log_message(
                "No configuration found. Please open settings to configure Twitch connection.",
                "WARNING"
            )
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            
            self.log_message(
                f"Configuration loaded for channel: {self.config.get('channel', 'unknown')}",
                "INFO"
            )
            
        except Exception as e:
            self.log_message(f"Failed to load configuration: {e}", "ERROR")
    
    def log_message(self, message: str, level: str = "INFO") -> None:
        """Add a message to the chat log with timestamp.
        
        Args:
            message: The message to log
            level: Log level (INFO, WARNING, ERROR, CHAT, SUCCESS, etc.)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Colour coding based on level
        level_colours = {
            "ERROR": "red",
            "WARNING": "orange",
            "SUCCESS": "green",
            "CHAT": "black",
            "INFO": "blue"
        }
        colour = level_colours.get(level, "black")
        
        formatted_message = f"[{timestamp}] [{level}] {message}\n"
        
        # Enable text widget, insert message with colour, disable again
        self.log_text.config(state=tk.NORMAL)
        
        # Insert with tag for colouring
        start_pos = self.log_text.index(tk.END)
        self.log_text.insert(tk.END, formatted_message)
        end_pos = self.log_text.index(tk.END)
        
        # Apply colour tag to the line
        self.log_text.tag_add(level, start_pos, end_pos)
        self.log_text.tag_config(level, foreground=colour)
        
        self.log_text.see(tk.END)  # Auto-scroll to bottom
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self) -> None:
        """Clear the chat log display."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log_message("Log cleared", "INFO")
    
    def toggle_connection(self) -> None:
        """Toggle connection to Twitch chat."""
        if self.is_connected:
            self.disconnect_from_twitch()
        else:
            self.connect_to_twitch()
    
    def connect_to_twitch(self) -> None:
        """Connect to Twitch IRC using configured credentials."""
        if not self.config:
            messagebox.showerror(
                "Configuration Missing",
                "No configuration found. Please configure settings first."
            )
            self.open_settings()
            return
        
        # Validate config has all required fields
        required_fields = ['username', 'oauth_token', 'client_id', 'client_secret', 'bot_id', 'channel']
        missing = [f for f in required_fields if not self.config.get(f)]
        if missing:
            messagebox.showerror(
                "Incomplete Configuration",
                f"Missing configuration fields: {', '.join(missing)}\n\n"
                "Please complete settings."
            )
            self.open_settings()
            return
        
        self.log_message("Checking OAuth token...", "INFO")
        
        # Check and refresh token if needed
        threading.Thread(target=self._check_and_connect, daemon=True).start()
    
    def _check_and_connect(self) -> None:
        """Check token validity and refresh if needed before connecting."""
        try:
            # Create token manager
            token_manager = TokenManager(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret'],
                config_path=self.config_path
            )
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Check token validity
            refresh_token = self.config.get('refresh_token')
            result = loop.run_until_complete(
                token_manager.ensure_valid_token(
                    self.config['oauth_token'],
                    refresh_token
                )
            )
            
            if result:
                access_token, new_refresh = result
                # Update config with new tokens
                self.config['oauth_token'] = access_token
                if new_refresh:
                    self.config['refresh_token'] = new_refresh
                
                # Save updated tokens to config file
                try:
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                    
                    config_data['oauth_token'] = access_token
                    if new_refresh:
                        config_data['refresh_token'] = new_refresh
                    
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(config_data, f, indent=2)
                    
                    logger.info("Saved refreshed tokens to config file")
                except Exception as e:
                    logger.error(f"Failed to save refreshed tokens: {e}")
                
                self.root.after(0, lambda: self.log_message("Token validated", "SUCCESS"))
                self.root.after(0, lambda: self.log_message("Connecting to Twitch...", "INFO"))
                
                # Start bot in separate thread
                self.bot_thread = threading.Thread(target=self._run_bot_thread)
                self.bot_thread.daemon = True
                self.bot_thread.start()
            else:
                # Token refresh failed - need new authorization
                self.root.after(
                    0,
                    lambda: self.log_message(
                        "Token expired and could not be refreshed. Please re-authenticate.",
                        "ERROR"
                    )
                )
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Authentication Required",
                        "Your OAuth token has expired and could not be refreshed.\n\n"
                        "Please open Chat Tools Settings and click 'Authenticate with Twitch' "
                        "to get a new token."
                    )
                )
                
            loop.close()
            
        except Exception as e:
            logger.error(f"Token check failed: {e}")
            self.root.after(
                0,
                lambda err=str(e): self.log_message(
                    f"Token check failed: {err}",
                    "ERROR"
                )
            )
    
    def _run_bot_thread(self) -> None:
        """Thread worker for running Twitch bot.
        
        Creates bot instance using extracted TwitchChatBot class and runs
        it in a separate thread with its own asyncio event loop.
        """
        try:
            # Create new event loop for this thread
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            
            # Create command handler
            self.command_handler = CommandHandler(
                config_getter=lambda: self.config,
                send_message_callback=self._async_send_message,
                log_callback=lambda msg: self.root.after(0, lambda m=msg: self.log_message(m, "SUCCESS"))
            )
            
            # Create auto-message handler
            self.auto_msg_handler = AutoMessageHandler(
                config_getter=lambda: self.config,
                send_message_callback=self._async_send_message,
                activity_tracker=self.chat_activity_timestamps,
                log_callback=lambda msg: self.root.after(0, lambda m=msg: self.log_message(m, "SUCCESS"))
            )
            
            # Create bot instance with callbacks
            self.bot = TwitchChatBot(
                config=self.config,
                on_ready_callback=self._on_bot_ready,
                on_message_callback=self._on_bot_message,
                on_error_callback=self._on_bot_error,
                command_handler=self.command_handler.handle_command,
                activity_tracker=self.chat_activity_timestamps
            )
            
            self.log_message(f"Bot created, connecting to Twitch...", "INFO")
            
            # Run bot with the OAuth token
            self.event_loop.run_until_complete(
                self.bot.start(token=self.config['oauth_token'])
            )
            
        except ImportError:
            self.root.after(
                0,
                lambda: self.log_message(
                    "twitchio library not installed. Install with: pip install twitchio",
                    "ERROR"
                )
            )
            self.is_connected = False
            self.root.after(0, self._update_connection_status)
            
        except Exception as e:
            error_msg = str(e)
            self.root.after(
                0,
                lambda msg=error_msg: self.log_message(
                    f"Connection failed: {msg}",
                    "ERROR"
                )
            )
            self.is_connected = False
            self.root.after(0, self._update_connection_status)
            
            import traceback
            traceback.print_exc()
    
    async def _async_send_message(self, message: str) -> None:
        """Async wrapper for sending messages via bot."""
        if self.bot:
            await self.bot.send_message(message)
    
    def _on_bot_ready(self) -> None:
        """Callback when bot is ready and connected."""
        self.is_connected = True
        self.root.after(0, self._update_connection_status)
        self.root.after(
            0,
            lambda: self.log_message(
                f"Connected to Twitch, monitoring #{self.config['channel']}",
                "SUCCESS"
            )
        )
        
        # Start auto-message handler
        if self.auto_msg_handler:
            self.auto_msg_handler.start()
    
    def _on_bot_message(self, username: str, content: str) -> None:
        """Callback when chat message received."""
        self.root.after(
            0,
            lambda u=username, c=content: self.log_message(
                f"{u}: {c}",
                "CHAT"
            )
        )
    
    def _on_bot_error(self, error_msg: str) -> None:
        """Callback when bot error occurs."""
        self.root.after(
            0,
            lambda e=error_msg: self.log_message(
                f"Bot error: {e}",
                "ERROR"
            )
        )
    
    def disconnect_from_twitch(self) -> None:
        """Disconnect from Twitch IRC."""
        self.log_message("Disconnecting from Twitch...", "INFO")
        
        # Stop auto-message handler
        if self.auto_msg_handler:
            self.auto_msg_handler.stop()
        
        if self.bot and self.event_loop:
            try:
                # Stop the bot gracefully
                future = asyncio.run_coroutine_threadsafe(
                    self.bot.close(),
                    self.event_loop
                )
                future.result(timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Bot close timed out, forcing shutdown")
            except OSError as e:
                # Suppress Windows overlapped I/O errors during shutdown
                if e.winerror != 6:  # Ignore "handle is invalid" errors
                    logger.warning(f"Error during disconnect: {e}")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        self.is_connected = False
        self.bot = None
        self.event_loop = None
        self.auto_msg_task = None
        self._update_connection_status()
        self.log_message("Disconnected from Twitch", "INFO")
    
    def _update_connection_status(self) -> None:
        """Update the connection status indicator."""
        if self.is_connected:
            self.status_label.config(
                text="● Connected",
                fg="#2ECC71"
            )
            self.connect_btn.config(
                text="Disconnect",
                bg="#E74C3C"
            )
        else:
            self.status_label.config(
                text="● Disconnected",
                fg="#E74C3C"
            )
            self.connect_btn.config(
                text="Connect",
                bg="#4CAF50"
            )
    
    def open_settings(self) -> None:
        """Open the chat tools settings window."""
        import subprocess
        import sys
        
        settings_path = Path(__file__).parent / "chat_tools_settings.py"
        
        try:
            subprocess.Popen([
                sys.executable,
                str(settings_path)
            ], cwd=str(Path(__file__).parent))
            
            self.log_message("Settings window opened", "INFO")
            
            # Reload config after a delay (user might save new settings)
            self.root.after(1000, self._load_config)
            
        except Exception as e:
            self.log_message(f"Failed to open settings: {e}", "ERROR")
    
    def _start_config_watcher(self) -> None:
        """Start watching config file for changes."""
        if not self.config_path.exists():
            return
        
        chat_tools_instance = self
        
        class ConfigFileHandler(FileSystemEventHandler):
            """Handler for config file changes."""
            
            def on_modified(self, event):
                """Called when config file is modified."""
                if event.src_path == str(chat_tools_instance.config_path):
                    logger.info(f"Config file changed, reloading...")
                    # Reload in main thread with small delay to ensure file write is complete
                    chat_tools_instance.root.after(500, chat_tools_instance._reload_config)
        
        # Create observer and start watching
        event_handler = ConfigFileHandler()
        self.config_observer = Observer()
        self.config_observer.schedule(
            event_handler,
            str(self.config_path.parent),
            recursive=False
        )
        self.config_observer.start()
        logger.info("Config file watcher started")
    
    def _reload_config(self) -> None:
        """Reload configuration from file without reconnecting."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                new_config = json.load(f)
            
            # Store old config for comparison
            old_config = self.config.copy() if self.config else {}
            
            # Update config
            self.config = new_config
            
            # Detect specific changes for logging
            changes = []
            
            # Check connection settings
            connection_keys = ["username", "oauth_token", "client_id", "client_secret", "bot_id", "channel"]
            if any(old_config.get(k) != new_config.get(k) for k in connection_keys):
                changes.append("[Connection tab] connection settings")
            
            # Check commands
            if old_config.get("commands") != new_config.get("commands"):
                num_commands = len(new_config.get("commands", []))
                changes.append(f"[Commands tab] commands ({num_commands} total)")
            
            # Check auto messages config
            if old_config.get("auto_messages") != new_config.get("auto_messages"):
                changes.append("[Auto Messages tab] auto-messages")
            
            if changes:
                self.log_message(
                    f"Config reloaded: {', '.join(changes)} updated",
                    "INFO"
                )
            else:
                self.log_message("Config reloaded (no changes detected)", "INFO")
        
        except Exception as e:
            self.log_message(f"Failed to reload config: {e}", "ERROR")
    
    def _stop_config_watcher(self) -> None:
        """Stop watching config file."""
        if self.config_observer:
            try:
                self.config_observer.stop()
                self.config_observer.join(timeout=2.0)
            except Exception:
                pass  # Suppress errors during shutdown
            finally:
                self.config_observer = None
                logger.info("Config file watcher stopped")
    
    def run(self) -> None:
        """Start the chat tools main loop."""
        self.log_message("Chat Tools started", "INFO")
        self.log_message(
            "Click 'Open Settings' to configure Twitch connection, then 'Connect' to start monitoring chat.",
            "INFO"
        )
        try:
            self.root.mainloop()
        finally:
            # Clean up gracefully on exit
            try:
                self._stop_config_watcher()
                if self.is_connected:
                    self.disconnect_from_twitch()
            except Exception:
                pass  # Suppress errors during cleanup


def main() -> None:
    """Main entry point for chat tools."""
    try:
        chat_tools = ChatTools()
        chat_tools.run()
    except KeyboardInterrupt:
        logger.info("Chat tools interrupted by user.")
    except Exception as e:
        logger.error(f"Error starting chat tools: {e}")


if __name__ == "__main__":
    main()
