"""
Chat Tools Settings GUI

Configuration interface for Twitch chat integration. Allows users to input
their Twitch credentials, test connection, and save settings for the chat tools.
"""

import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext
import json
from pathlib import Path
from typing import Optional, Any
import asyncio
import threading
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from logger_setup import setup_logger

logger = setup_logger(__name__)

# Import tab classes
from chat_tools_settings_tabs import ConnectionTab, CommandsTab, AutoMessagesTab


def create_link_label(parent: tk.Frame, text: str, url: str, row: int, column: int, **grid_kwargs) -> tk.Label:
    """Create a clickable link label."""
    label = tk.Label(
        parent,
        text=text,
        font=("Arial", 8, "underline"),
        fg="blue",
        cursor="hand2"
    )
    label.grid(row=row, column=column, **grid_kwargs)
    label.bind("<Button-1>", lambda e: webbrowser.open(url))
    return label


class ChatToolsSettings:
    """Settings GUI for configuring Twitch chat connection."""
    
    def __init__(self) -> None:
        """Initialise the chat tools settings GUI."""
        self.root = tk.Tk()
        self.root.title("Chat Tools - Settings")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        self.config_path = Path(__file__).parent / "config" / "chat_tools_config.json"
        
        # OAuth callback storage
        self.oauth_callback_data: Optional[dict] = None
        self.oauth_server: Optional[HTTPServer] = None
        
        # Commands tab state
        self.commands_list: list[dict[str, Any]] = []
        self.selected_command_index: Optional[int] = None
        
        # Auto messages tab state
        self.auto_messages_list: list[dict[str, Any]] = []
        self.selected_message_index: Optional[int] = None
        
        # Ensure config directory exists
        self.config_path.parent.mkdir(exist_ok=True)
        
        self._create_ui()
        self._load_existing_config()
    
    def _create_ui(self) -> None:
        """Create the settings UI components."""
        # Title
        title_label = tk.Label(
            self.root,
            text="Twitch Chat Configuration",
            font=("Arial", 16, "bold"),
            pady=15
        )
        title_label.pack()
        
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Create tabs using tab classes
        self.connection_tab = ConnectionTab(
            self.notebook,
            start_oauth_callback=self.start_oauth_flow,
            test_connection_callback=self.test_connection
        )
        
        self.commands_tab = CommandsTab(
            self.notebook,
            on_command_selected_callback=self._on_command_selected,
            add_command_callback=self._add_command,
            remove_command_callback=self._remove_command,
            save_command_callback=self._save_current_command
        )
        
        self.auto_messages_tab = AutoMessagesTab(
            self.notebook,
            on_message_selected_callback=self._on_message_selected,
            add_message_callback=self._add_auto_message,
            remove_message_callback=self._remove_auto_message,
            save_message_callback=self._save_current_message
        )
        
        # Bottom button frame (applies to all tabs)
        button_frame = tk.Frame(self.root, pady=10)
        button_frame.pack()
        
        # Save button
        save_btn = tk.Button(
            button_frame,
            text="Save All Settings",
            command=self.save_settings,
            width=20,
            font=("Arial", 10, "bold"),
            bg="#4CAF50",
            fg="white"
        )
        save_btn.pack(side=tk.LEFT, padx=10)
        
        # Close button
        close_btn = tk.Button(
            button_frame,
            text="Close",
            command=self.root.quit,
            width=15,
            font=("Arial", 10)
        )
        close_btn.pack(side=tk.LEFT, padx=10)
    
    def _on_command_selected(self, event: Any) -> None:
        """Handle command selection in listbox."""
        selection = self.commands_tab.commands_listbox.curselection()
        if not selection:
            return
        
        self.selected_command_index = selection[0]
        command = self.commands_list[self.selected_command_index]
        
        # Populate editor fields
        self.commands_tab.cmd_name_entry.delete(0, tk.END)
        self.commands_tab.cmd_name_entry.insert(0, command.get("name", ""))
        
        self.commands_tab.cmd_triggers_entry.delete(0, tk.END)
        self.commands_tab.cmd_triggers_entry.insert(0, " ".join(command.get("triggers", [])))
        
        self.commands_tab.cmd_response_text.delete("1.0", tk.END)
        self.commands_tab.cmd_response_text.insert("1.0", command.get("response", ""))
        
        self.commands_tab.cmd_permission_var.set(command.get("permission", "everyone"))
        self.commands_tab.cmd_cooldown_var.set(command.get("cooldown", 30))
        self.commands_tab.cmd_enabled_var.set(command.get("enabled", True))
    
    def _on_message_selected(self, event: Any) -> None:
        """Handle auto message selection in listbox."""
        selection = self.auto_messages_tab.messages_listbox.curselection()
        if not selection:
            return
        
        self.selected_message_index = selection[0]
        message = self.auto_messages_list[self.selected_message_index]
        
        # Populate editor fields
        self.auto_messages_tab.msg_text.delete("1.0", tk.END)
        self.auto_messages_tab.msg_text.insert("1.0", message.get("text", ""))
        
        self.auto_messages_tab.msg_enabled_var.set(message.get("enabled", True))
    
    def _add_command(self) -> None:
        """Add a new blank command."""
        new_command = {
            "name": "New Command",
            "triggers": ["!newcmd"],
            "response": "",
            "permission": "everyone",
            "cooldown": 30,
            "enabled": True
        }
        
        self.commands_list.append(new_command)
        self._refresh_commands_list()
        
        # Select the new command
        self.commands_tab.commands_listbox.selection_clear(0, tk.END)
        self.commands_tab.commands_listbox.selection_set(tk.END)
        self.commands_tab.commands_listbox.see(tk.END)
        self._on_command_selected(None)
    
    def _remove_command(self) -> None:
        """Remove the selected command."""
        if self.selected_command_index is None:
            messagebox.showwarning(
                "No Selection",
                "Please select a command to remove."
            )
            return
        
        command = self.commands_list[self.selected_command_index]
        
        if messagebox.askyesno(
            "Confirm Removal",
            f"Remove command '{command.get('name', 'Unknown')}'?"
        ):
            self.commands_list.pop(self.selected_command_index)
            self.selected_command_index = None
            self._refresh_commands_list()
            self._clear_command_editor()
    
    def _add_auto_message(self) -> None:
        """Add a new blank auto message."""
        new_message = {
            "text": "",
            "enabled": True
        }
        
        self.auto_messages_list.append(new_message)
        self._refresh_messages_list()
        
        # Select the new message
        self.auto_messages_tab.messages_listbox.selection_clear(0, tk.END)
        self.auto_messages_tab.messages_listbox.selection_set(tk.END)
        self.auto_messages_tab.messages_listbox.see(tk.END)
        self._on_message_selected(None)
    
    def _remove_auto_message(self) -> None:
        """Remove the selected auto message."""
        if self.selected_message_index is None:
            messagebox.showwarning(
                "No Selection",
                "Please select a message to remove."
            )
            return
        
        message = self.auto_messages_list[self.selected_message_index]
        preview = message.get("text", "")[:50]
        
        if messagebox.askyesno(
            "Confirm Removal",
            f"Remove message '{preview}...'?"
        ):
            self.auto_messages_list.pop(self.selected_message_index)
            self.selected_message_index = None
            self._refresh_messages_list()
            self._clear_message_editor()
    
    def _save_current_command(self) -> None:
        """Save the current command from editor."""
        # Get values from editor
        name = self.commands_tab.cmd_name_entry.get().strip()
        triggers_text = self.commands_tab.cmd_triggers_entry.get().strip()
        response = self.commands_tab.cmd_response_text.get("1.0", tk.END).strip()
        permission = self.commands_tab.cmd_permission_var.get()
        cooldown = self.commands_tab.cmd_cooldown_var.get()
        enabled = self.commands_tab.cmd_enabled_var.get()
        
        # Validate
        if not name:
            messagebox.showerror("Validation Error", "Command name cannot be empty.")
            return
        
        if not triggers_text:
            messagebox.showerror("Validation Error", "At least one trigger is required.")
            return
        
        # Parse triggers
        triggers = [t.strip() for t in triggers_text.split() if t.strip()]
        
        # Validate triggers
        for trigger in triggers:
            if not trigger.startswith("!"):
                messagebox.showerror(
                    "Validation Error",
                    f"Trigger '{trigger}' must start with '!'"
                )
                return
            
            if not trigger[1:].replace("_", "").isalnum():
                messagebox.showerror(
                    "Validation Error",
                    f"Trigger '{trigger}' must be alphanumeric (underscores allowed)"
                )
                return
        
        # Check for duplicate triggers across all commands
        for idx, cmd in enumerate(self.commands_list):
            if idx == self.selected_command_index:
                continue  # Skip current command
            
            for trigger in triggers:
                if trigger in cmd.get("triggers", []):
                    messagebox.showerror(
                        "Validation Error",
                        f"Trigger '{trigger}' is already used by command '{cmd.get('name', 'Unknown')}'"
                    )
                    return
        
        if not response:
            messagebox.showerror("Validation Error", "Response cannot be empty.")
            return
        
        # Save to command
        if self.selected_command_index is not None:
            self.commands_list[self.selected_command_index] = {
                "name": name,
                "triggers": triggers,
                "response": response,
                "permission": permission,
                "cooldown": cooldown,
                "enabled": enabled
            }
            self._refresh_commands_list()
            messagebox.showinfo("Success", "Command saved successfully!")
        else:
            messagebox.showwarning("No Selection", "Please select a command first.")
    
    def _save_current_message(self) -> None:
        """Save the current auto message from editor."""
        text = self.auto_messages_tab.msg_text.get("1.0", tk.END).strip()
        enabled = self.auto_messages_tab.msg_enabled_var.get()
        
        # Validate
        if not text:
            messagebox.showerror("Validation Error", "Message text cannot be empty.")
            return
        
        # Save to message
        if self.selected_message_index is not None:
            self.auto_messages_list[self.selected_message_index] = {
                "text": text,
                "enabled": enabled
            }
            self._refresh_messages_list()
            messagebox.showinfo("Success", "Message saved successfully!")
        else:
            messagebox.showwarning("No Selection", "Please select a message first.")
    
    def _refresh_commands_list(self) -> None:
        """Refresh the commands listbox."""
        self.commands_tab.commands_listbox.delete(0, tk.END)
        for command in self.commands_list:
            name = command.get("name", "Unnamed")
            status = "✓" if command.get("enabled", True) else "✗"
            self.commands_tab.commands_listbox.insert(tk.END, f"{status} {name}")
    
    def _refresh_messages_list(self) -> None:
        """Refresh the auto messages listbox."""
        self.auto_messages_tab.messages_listbox.delete(0, tk.END)
        for message in self.auto_messages_list:
            text = message.get("text", "")
            preview = text[:30] + "..." if len(text) > 30 else text
            status = "✓" if message.get("enabled", True) else "✗"
            self.auto_messages_tab.messages_listbox.insert(tk.END, f"{status} {preview}")
    
    def _clear_command_editor(self) -> None:
        """Clear the command editor fields."""
        self.commands_tab.cmd_name_entry.delete(0, tk.END)
        self.commands_tab.cmd_triggers_entry.delete(0, tk.END)
        self.commands_tab.cmd_response_text.delete("1.0", tk.END)
        self.commands_tab.cmd_permission_var.set("everyone")
        self.commands_tab.cmd_cooldown_var.set(30)
        self.commands_tab.cmd_enabled_var.set(True)
    
    def _clear_message_editor(self) -> None:
        """Clear the message editor fields."""
        self.auto_messages_tab.msg_text.delete("1.0", tk.END)
        self.auto_messages_tab.msg_enabled_var.set(True)
    
    def _load_existing_config(self) -> None:
        """Load existing configuration if available."""
        if not self.config_path.exists():
            return
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            # Populate connection fields
            self.connection_tab.username_entry.insert(0, config.get("username", ""))
            
            # OAuth token is readonly, need to enable temporarily
            oauth_token = config.get("oauth_token", "")
            if oauth_token:
                self.connection_tab.oauth_entry.config(state="normal")
                self.connection_tab.oauth_entry.insert(0, oauth_token)
                self.connection_tab.oauth_entry.config(state="readonly")
            
            self.connection_tab.client_id_entry.insert(0, config.get("client_id", ""))
            self.connection_tab.client_secret_entry.insert(0, config.get("client_secret", ""))
            self.connection_tab.bot_id_entry.insert(0, config.get("bot_id", ""))
            self.connection_tab.channel_entry.insert(0, config.get("channel", ""))
            
            # Load commands
            self.commands_list = config.get("commands", [])
            self._refresh_commands_list()
            
            # Load auto messages
            auto_msg_config = config.get("auto_messages", {})
            self.auto_messages_tab.auto_msg_master_enabled_var.set(
                auto_msg_config.get("enabled", True)
            )
            self.auto_messages_tab.auto_msg_interval_var.set(
                auto_msg_config.get("post_interval_minutes", 20)
            )
            self.auto_messages_tab.auto_msg_min_activity_var.set(
                auto_msg_config.get("min_chat_activity", 5)
            )
            self.auto_messages_tab.auto_msg_activity_window_var.set(
                auto_msg_config.get("activity_window_minutes", 5)
            )
            self.auto_messages_tab.auto_msg_random_var.set(
                auto_msg_config.get("random_order", True)
            )
            self.auto_messages_list = auto_msg_config.get("messages", [])
            self._refresh_messages_list()
            
        except Exception as e:
            logger.error(f"Failed to load existing config: {e}")
    
    def start_oauth_flow(self) -> None:
        """Start OAuth2 authorization flow with Twitch."""
        client_id = self.connection_tab.client_id_entry.get().strip()
        
        if not client_id:
            messagebox.showerror(
                "Missing Client ID",
                "Please enter your Client ID before authorizing.\n\n"
                "Get it from: https://dev.twitch.tv/console/apps"
            )
            return
        
        # Start OAuth flow in separate thread
        thread = threading.Thread(target=self._oauth_flow_thread, args=(client_id,))
        thread.daemon = True
        thread.start()
    
    def _oauth_flow_thread(self, client_id: str) -> None:
        """Thread worker for Twitch OAuth flow.
        
        Implements Twitch's implicit grant OAuth flow using a local HTTP server
        to capture the access token. This is a complex two-step process required
        because Twitch returns the token in the URL fragment (after #), which
        browsers don't send to servers.
        
        OAuth Flow Process:
        1. Opens browser to Twitch OAuth URL with client_id and redirect_uri
        2. User authorises the application on Twitch
        3. Twitch redirects to http://localhost:8080 with token in URL fragment
        4. Local HTTP server serves HTML page with JavaScript
        5. JavaScript extracts token from window.location.hash
        6. JavaScript makes fetch() call to /callback with token as query param
        7. Server captures token from query string and stores it
        8. Token is updated in GUI via root.after() for thread safety
        
        Why Two HTTP Requests Are Needed:
        - First request (/) serves the HTML/JavaScript extraction page
        - Second request (/callback) receives the extracted token
        - This workaround is necessary because URL fragments are client-side only
        
        Server Configuration:
        - Listens on localhost:8080
        - Timeout: None (blocks until token received)
        - Handles exactly 2 requests then shuts down
        
        Current Limitations (TODO):
        - Single OAuth token (bot account only)
        - Missing broadcaster OAuth for advanced features
        - No token refresh mechanism
        - No token expiration handling
        - See lines 1125-1147 for dual OAuth implementation plan
        
        Thread Safety:
        - Uses class instance variable to pass token between handler and thread
        - GUI updates via root.after() to avoid tkinter threading issues
        
        Error Handling:
        - Catches all exceptions and displays error dialog
        - Prints debug output to console for troubleshooting
        """
        try:
            # Create OAuth callback handler
            settings_instance = self
            
            class OAuthCallbackHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    # Parse the callback URL
                    parsed = urllib.parse.urlparse(self.path)
                    params = urllib.parse.parse_qs(parsed.query)
                    
                    # Log only the path component to avoid leaking tokens in query string
                    logger.debug(f"Callback received: {parsed.path}")
                    
                    # Redact potentially sensitive query parameters (e.g., tokens) before logging
                    redacted_params = {
                        key: (["***REDACTED***"] if "token" in key.lower() else value)
                        for key, value in params.items()
                    }
                    logger.debug(f"Query params: {redacted_params}")
                    
                    # Check if this is the token callback (from JavaScript)
                    if '/callback' in self.path and 'access_token' in params:
                        token = params['access_token'][0]
                        logger.info("OAuth token received.")
                        settings_instance.oauth_callback_data = {
                            'token': token,
                            'success': True
                        }
                        
                        # Send minimal response
                        self.send_response(200)
                        self.send_header('Content-type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(b'OK')
                        
                    elif 'error' in params:
                        # Error in OAuth
                        error = params['error'][0]
                        logger.error(f"OAuth error: {error}")
                        settings_instance.oauth_callback_data = {
                            'success': False,
                            'error': error
                        }
                        
                        # Send error page
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(f'''
                            <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                                <h1 style="color: red;">Authorization Failed</h1>
                                <p>Error: {error}</p>
                                <p>Please close this window and try again.</p>
                            </body></html>
                        '''.encode())
                        
                    else:
                        # Initial redirect from Twitch - extract fragment with JavaScript
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'''
                            <html>
                            <head><title>Twitch Authorization</title></head>
                            <body style="font-family: Arial; text-align: center; padding: 50px;">
                                <h1 style="color: #9146FF;">Processing Authorization...</h1>
                                <p>Please wait...</p>
                                <script>
                                    // Extract token from URL fragment
                                    const hash = window.location.hash.substring(1);
                                    const params = new URLSearchParams(hash);
                                    const token = params.get('access_token');
                                    const error = params.get('error');
                                    
                                    if (token) {
                                        // Send token to server via query string
                                        fetch('/callback?access_token=' + encodeURIComponent(token))
                                            .then(() => {
                                                document.body.innerHTML = `
                                                    <h1 style="color: #9146FF;">Authorization Successful!</h1>
                                                    <p>You can close this window and return to the application.</p>
                                                `;
                                            })
                                            .catch(err => {
                                                document.body.innerHTML = `
                                                    <h1 style="color: red;">Error</h1>
                                                    <p>Failed to send token. Please try again.</p>
                                                `;
                                            });
                                    } else if (error) {
                                        document.body.innerHTML = `
                                            <h1 style="color: red;">Authorization Failed</h1>
                                            <p>Error: ${error}</p>
                                            <p>Please close this window and try again.</p>
                                        `;
                                    } else {
                                        document.body.innerHTML = `
                                            <h1 style="color: orange;">No Token Received</h1>
                                            <p>No authorization data found. Please try again.</p>
                                        `;
                                    }
                                </script>
                            </body>
                            </html>
                        ''')
                
                def log_message(self, format, *args):
                    # Suppress server logs
                    pass
            
            # Start local server
            port = 8080
            self.oauth_server = HTTPServer(('localhost', port), OAuthCallbackHandler)
            
            # Build OAuth URL
            redirect_uri = f"http://localhost:{port}"
            # TODO: Implement dual OAuth flow for bot account and streamer account
            # TODO: Current flow only authenticates bot account, which limits access to streamer's channel data
            # TODO: Bot account needs these scopes for basic functionality:
            # TODO:   - user:read:chat (read messages via EventSub)
            # TODO:   - user:write:chat (send messages to chat)
            # TODO:   - moderator:read:followers (read followers as moderator)
            # TODO: Streamer account needs these scopes for full channel data access:
            # TODO:   - channel:read:subscriptions (read subscriber list and events)
            # TODO:   - channel:read:predictions (read prediction events)
            # TODO:   - channel:read:polls (read poll events)
            # TODO:   - channel:read:hype_train (read hype train events)
            # TODO:   - channel:read:redemptions (read channel point redemptions)
            # TODO:   - bits:read (read bits/cheer events)
            # TODO: Implementation plan for dual OAuth:
            # TODO:   1. Add separate "Authenticate Bot" and "Authenticate Streamer" buttons in settings
            # TODO:   2. Store both tokens in config (bot_oauth_token, streamer_oauth_token)
            # TODO:   3. Use bot token for chat operations (read/write messages)
            # TODO:   4. Use streamer token for channel data queries (subs, predictions, polls, etc.)
            # TODO:   5. Add validation to ensure both tokens are present before connecting
            # TODO:   6. Handle token refresh separately for both accounts
            # TODO:   7. Display which account is authenticated in settings UI
            # TODO: For now, using single bot account OAuth with moderator permissions
            # TODO: Bot must be moderator in streamer's channel for moderator:read:followers to work
            
            # Comprehensive scopes for chat, stream info, and events
            scopes = (
                "user:read:chat "
                "user:write:chat "
                "channel:read:subscriptions "
                "moderator:read:followers "
                "channel:read:predictions "
                "channel:read:polls "
                "channel:read:hype_train "
                "channel:read:redemptions "
                "bits:read"
            )
            
            auth_url = (
                f"https://id.twitch.tv/oauth2/authorize"
                f"?client_id={client_id}"
                f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
                f"&response_type=token"
                f"&scope={urllib.parse.quote(scopes)}"
            )
            
            logger.info("Opening browser for OAuth authorisation...")
            logger.debug(f"Auth URL: {auth_url}")
            
            # Open browser
            webbrowser.open(auth_url)
            
            # Wait for callback (with timeout)
            self.oauth_callback_data = None
            
            # Handle two requests: initial page load + token callback
            logger.debug("Waiting for initial callback...")
            self.oauth_server.handle_request()  # Initial page load
            
            if not self.oauth_callback_data:
                logger.debug("Waiting for token callback...")
                self.oauth_server.handle_request()  # Token callback from JavaScript
            
            # Process result
            if self.oauth_callback_data and self.oauth_callback_data.get('success'):
                token = self.oauth_callback_data['token']
                logger.info("OAuth token received successfully")
                
                # Update UI in main thread
                self.root.after(0, lambda: self._update_oauth_token(token))
            else:
                error = self.oauth_callback_data.get('error', 'Unknown error') if self.oauth_callback_data else 'Timeout'
                logger.error(f"OAuth failed: {error}")
                
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Authorization Failed",
                        f"OAuth authorization failed: {error}"
                    )
                )
            
        except Exception as e:
            logger.error(f"OAuth flow error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            self.root.after(
                0,
                lambda msg=str(e): messagebox.showerror(
                    "OAuth Error",
                    f"Error during OAuth flow:\n{msg}"
                )
            )
        finally:
            if self.oauth_server:
                self.oauth_server.server_close()
    
    def _update_oauth_token(self, token: str) -> None:
        """Update OAuth token field in UI."""
        self.connection_tab.oauth_entry.config(state="normal")
        self.connection_tab.oauth_entry.delete(0, tk.END)
        self.connection_tab.oauth_entry.insert(0, token)
        self.connection_tab.oauth_entry.config(state="readonly")
        
        messagebox.showinfo(
            "Authorization Successful",
            "OAuth token received successfully!\n\n"
            "Next: Enter your Bot ID below.\n"
            "Get it from: https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/\n\n"
            "Then test the connection or save settings."
        )
    
    def test_connection(self) -> None:
        """Test connection to Twitch with provided credentials."""
        username = self.connection_tab.username_entry.get().strip()
        oauth_token = self.connection_tab.oauth_entry.get().strip()
        client_id = self.connection_tab.client_id_entry.get().strip()
        client_secret = self.connection_tab.client_secret_entry.get().strip()
        bot_id = self.connection_tab.bot_id_entry.get().strip()
        channel = self.connection_tab.channel_entry.get().strip()
        
        # Basic validation
        if not all([username, oauth_token, client_id, client_secret, bot_id, channel]):
            messagebox.showerror(
                "Validation Error",
                "All fields are required to test connection."
            )
            return
        
        # Validate bot_id is numeric
        if not bot_id.isdigit():
            messagebox.showerror(
                "Validation Error",
                f"Bot ID must be numeric (got: {bot_id}).\n\n"
                "Get your numeric Bot ID from:\n"
                "https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/"
            )
            return
        
        # OAuth2 tokens don't need oauth: prefix (that's for IRC tokens only)
        # Remove it if present
        if oauth_token.startswith("oauth:"):
            oauth_token = oauth_token[6:]
        
        # Run connection test in separate thread to avoid blocking GUI
        thread = threading.Thread(
            target=self._test_connection_thread,
            args=(username, oauth_token, client_id, client_secret, bot_id, channel)
        )
        thread.daemon = True
        thread.start()
    
    def _test_connection_thread(
        self,
        username: str,
        oauth_token: str,
        client_id: str,
        client_secret: str,
        bot_id: str,
        channel: str
    ) -> None:
        """Thread worker for testing Twitch connection.
        
        Creates a temporary bot instance to validate credentials and connection
        without starting the full chat bot. Useful for debugging auth issues.
        
        Process:
        1. Creates temporary TwitchIO bot with provided credentials
        2. Attempts to connect to Twitch API
        3. Joins specified channel
        4. Waits up to 10 seconds for successful connection
        5. Reports success/failure back to GUI via callback
        
        Timeout Mechanism:
        - Uses asyncio.wait_for() with 10-second timeout
        - Prevents hanging on invalid credentials or network issues
        - Timeout error is caught and reported as connection failure
        
        Callback System:
        - Uses root.after() for thread-safe GUI updates
        - Displays success message in green
        - Displays errors in red
        - Async result handling via temporary bot instance
        
        Validation:
        - Bot ID must be numeric (raises ValueError if not)
        - OAuth token must be valid Twitch access token
        - Client ID/Secret must match registered Twitch app
        - Channel must exist and be accessible
        
        Cleanup:
        - Bot instance is temporary and discarded after test
        - Does not interfere with main bot connection
        - Event loop created specifically for this test
        """
        try:
            # Try importing twitchio
            try:
                from twitchio.ext import commands
            except ImportError:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Missing Dependency",
                        "twitchio library not installed.\n\n"
                        "Install with: pip install twitchio"
                    )
                )
                return
            
            # Create temporary bot for testing
            class TestBot(commands.Bot):
                def __init__(self, test_callback):
                    super().__init__(
                        token=oauth_token,
                        prefix='!',
                        initial_channels=[channel],
                        client_id=client_id,
                        client_secret=client_secret,
                        bot_id=bot_id
                    )
                    self.test_callback = test_callback
                    self.connection_made = False
                
                async def event_ready(self):
                    # Connection successful
                    if not self.connection_made:
                        self.connection_made = True
                        self.test_callback(True, f"Successfully connected to #{channel}")
                        await self.close()
            
            # Run the test
            success = [False, "Connection timeout"]
            
            def test_callback(result: bool, message: str):
                success[0] = result
                success[1] = message
            
            # Create and run bot with timeout
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            bot = TestBot(test_callback)
            
            try:
                # Run with timeout
                loop.run_until_complete(
                    asyncio.wait_for(bot.start(), timeout=10.0)
                )
            except asyncio.TimeoutError:
                success[0] = False
                success[1] = "Connection timeout - check your credentials"
            except Exception as e:
                success[0] = False
                success[1] = f"Connection failed: {str(e)}"
            finally:
                loop.close()
            
            # Show result in GUI thread
            if success[0]:
                logger.info(f"Connection test successful: {success[1]}")
                self.root.after(
                    0,
                    lambda msg=success[1]: messagebox.showinfo(
                        "Connection Successful",
                        msg
                    )
                )
            else:
                logger.error(f"Connection test failed: {success[1]}")
                self.root.after(
                    0,
                    lambda msg=success[1]: messagebox.showerror(
                        "Connection Failed",
                        msg
                    )
                )
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error testing connection: {error_msg}")
            import traceback
            traceback.print_exc()
            self.root.after(
                0,
                lambda msg=error_msg: messagebox.showerror(
                    "Test Error",
                    f"Error testing connection:\n{msg}"
                )
            )
    
    def save_settings(self) -> None:
        """Save Twitch configuration to file."""
        username = self.connection_tab.username_entry.get().strip()
        
        # OAuth entry is readonly, need to get value differently
        self.connection_tab.oauth_entry.config(state="normal")
        oauth_token = self.connection_tab.oauth_entry.get().strip()
        self.connection_tab.oauth_entry.config(state="readonly")
        
        client_id = self.connection_tab.client_id_entry.get().strip()
        client_secret = self.connection_tab.client_secret_entry.get().strip()
        bot_id = self.connection_tab.bot_id_entry.get().strip()
        channel = self.connection_tab.channel_entry.get().strip()
        
        # Validate connection fields
        if not all([username, oauth_token, client_id, client_secret, bot_id, channel]):
            messagebox.showerror(
                "Validation Error",
                "All connection fields are required. Please fill in all fields.\n\n"
                "Use 'Authorise with Twitch' button to get OAuth token."
            )
            return
        
        # Remove # from channel name if present
        if channel.startswith("#"):
            channel = channel[1:]
        
        # Create configuration dictionary
        config = {
            "username": username,
            "oauth_token": oauth_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "bot_id": bot_id,
            "channel": channel,
            "commands": self.commands_list,
            "auto_messages": {
                "enabled": self.auto_messages_tab.auto_msg_master_enabled_var.get(),
                "post_interval_minutes": self.auto_messages_tab.auto_msg_interval_var.get(),
                "min_chat_activity": self.auto_messages_tab.auto_msg_min_activity_var.get(),
                "activity_window_minutes": self.auto_messages_tab.auto_msg_activity_window_var.get(),
                "random_order": self.auto_messages_tab.auto_msg_random_var.get(),
                "messages": self.auto_messages_list
            }
        }
        
        try:
            # Save to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo(
                "Settings Saved",
                f"Chat tools configuration saved successfully to:\n{self.config_path}"
            )
            
        except Exception as e:
            messagebox.showerror(
                "Save Error",
                f"Failed to save settings:\n{e}"
            )
    
    def run(self) -> None:
        """Start the settings GUI main loop."""
        self.root.mainloop()


def main() -> None:
    """Main entry point for chat tools settings."""
    try:
        settings_gui = ChatToolsSettings()
        settings_gui.run()
    except KeyboardInterrupt:
        logger.info("Settings interrupted by user")
    except Exception as e:
        logger.error(f"Error starting settings: {e}")


if __name__ == "__main__":
    main()
