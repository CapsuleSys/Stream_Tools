"""Connection Tab for Chat Tools Settings GUI.

Handles Twitch bot authentication and connection configuration.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable


def create_link_label(parent: tk.Frame, text: str, url: str, row: int, column: int, **grid_kwargs) -> tk.Label:
    """Create a clickable link label.
    
    Args:
        parent: Parent frame
        text: Display text for the link
        url: URL to open when clicked
        row: Grid row position
        column: Grid column position
        **grid_kwargs: Additional grid configuration options
        
    Returns:
        The created label widget
    """
    import webbrowser
    
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


class ConnectionTab:
    """Twitch connection configuration tab.
    
    Provides UI for OAuth authentication and bot connection settings.
    Users configure:
    - Bot username and credentials
    - OAuth token (via authorization flow)
    - Channel to join
    - Bot ID for API calls
    """
    
    def __init__(
        self,
        parent_frame: ttk.Notebook,
        start_oauth_callback: Callable[[], None],
        test_connection_callback: Callable[[], None]
    ) -> None:
        """Initialize the connection tab.
        
        Args:
            parent_frame: The notebook widget to add this tab to
            start_oauth_callback: Function to call when OAuth button clicked
            test_connection_callback: Function to call when test connection clicked
        """
        self.frame = tk.Frame(parent_frame, padx=40, pady=20)
        parent_frame.add(self.frame, text="Connection")
        
        self.start_oauth_callback = start_oauth_callback
        self.test_connection_callback = test_connection_callback
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Create all widgets for the connection tab."""
        # Main form frame
        form_frame = tk.Frame(self.frame)
        form_frame.pack(fill=tk.BOTH, expand=True)
        
        # Username field
        tk.Label(
            form_frame,
            text="Twitch Username:",
            font=("Arial", 11)
        ).grid(row=0, column=0, sticky="w", pady=10)
        
        self.username_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        self.username_entry.grid(row=0, column=1, pady=10, padx=10)
        
        # Client ID field (needed first for OAuth)
        tk.Label(
            form_frame,
            text="Client ID:",
            font=("Arial", 11)
        ).grid(row=1, column=0, sticky="w", pady=10)
        
        self.client_id_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        self.client_id_entry.grid(row=1, column=1, pady=10, padx=10)
        
        # Client Secret field
        tk.Label(
            form_frame,
            text="Client Secret:",
            font=("Arial", 11)
        ).grid(row=2, column=0, sticky="w", pady=10)
        
        self.client_secret_entry = tk.Entry(
            form_frame,
            width=30,
            font=("Arial", 11),
            show="*"
        )
        self.client_secret_entry.grid(row=2, column=1, pady=10, padx=10)
        
        # Help text for app credentials (clickable link)
        create_link_label(
            form_frame,
            "Register app at: https://dev.twitch.tv/console/apps",
            "https://dev.twitch.tv/console/apps",
            row=3,
            column=1,
            sticky="w",
            padx=10
        )
        
        # Redirect URI help text
        redirect_help = tk.Label(
            form_frame,
            text="⚠ Add redirect URI: http://localhost:8080",
            font=("Arial", 8),
            fg="red"
        )
        redirect_help.grid(row=4, column=1, sticky="w", padx=10, pady=(0, 5))
        
        # OAuth authorize button
        oauth_btn = tk.Button(
            form_frame,
            text="🔑 Authorize with Twitch",
            command=self.start_oauth_callback,
            font=("Arial", 10, "bold"),
            bg="#9146FF",
            fg="white",
            width=28
        )
        oauth_btn.grid(row=5, column=1, pady=15, padx=10)
        
        # OAuth token field (read-only, populated by OAuth)
        tk.Label(
            form_frame,
            text="OAuth Token:",
            font=("Arial", 11)
        ).grid(row=6, column=0, sticky="w", pady=10)
        
        self.oauth_entry = tk.Entry(
            form_frame,
            width=30,
            font=("Arial", 11),
            show="*",
            state="readonly"
        )
        self.oauth_entry.grid(row=6, column=1, pady=10, padx=10)
        
        # Help text for OAuth
        oauth_help = tk.Label(
            form_frame,
            text="Use 'Authorize with Twitch' button above",
            font=("Arial", 8),
            fg="grey"
        )
        oauth_help.grid(row=7, column=1, sticky="w", padx=10)
        
        # Bot ID field
        tk.Label(
            form_frame,
            text="Bot ID:",
            font=("Arial", 11)
        ).grid(row=8, column=0, sticky="w", pady=10)
        
        self.bot_id_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        self.bot_id_entry.grid(row=8, column=1, pady=10, padx=10)
        
        # Bot ID help text (clickable link)
        create_link_label(
            form_frame,
            "Get Bot ID: streamweasels.com/tools/convert-twitch-username-to-user-id",
            "https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/",
            row=9,
            column=1,
            sticky="w",
            padx=10,
            pady=(0, 10)
        )
        
        # Channel field
        tk.Label(
            form_frame,
            text="Channel to Join:",
            font=("Arial", 11)
        ).grid(row=10, column=0, sticky="w", pady=10)
        
        self.channel_entry = tk.Entry(form_frame, width=30, font=("Arial", 11))
        self.channel_entry.grid(row=10, column=1, pady=10, padx=10)
        
        # Channel help text
        channel_help = tk.Label(
            form_frame,
            text="Enter channel name without #",
            font=("Arial", 8),
            fg="grey"
        )
        channel_help.grid(row=11, column=1, sticky="w", padx=10)
        
        # Tab-specific buttons
        tab_button_frame = tk.Frame(self.frame, pady=15)
        tab_button_frame.pack()
        
        # Test connection button
        test_btn = tk.Button(
            tab_button_frame,
            text="Test Connection",
            command=self.test_connection_callback,
            width=15,
            font=("Arial", 10),
            bg="#FFA500",
            fg="white"
        )
        test_btn.pack(side=tk.LEFT, padx=10)
