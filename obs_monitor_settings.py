"""Settings GUI for OBS Scene Monitor configuration.

Provides a tkinter interface for configuring OBS WebSocket connection
settings and scene-to-text-file mappings.
"""

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from logger_setup import setup_logger

logger = setup_logger(__name__)


class OBSMonitorSettings:
    """Settings GUI for OBS scene monitor."""

    def __init__(self, config_path: str = "config/obs_config.json") -> None:
        """Initialise OBS monitor settings GUI.
        
        Args:
            config_path: Path to OBS configuration file
        """
        self.config_path: Path = Path(config_path)
        self.config: dict[str, Any] = {}
        self.text_files: list[str] = []
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("OBS Scene Monitor Settings")
        self.root.geometry("650x650")
        
        # Load configuration
        self._load_config()
        
        # Discover available text files
        self._discover_text_files()
        
        # Build UI
        self._create_widgets()
        
        # Load current values into widgets
        self._populate_widgets()
        
    def _load_config(self) -> None:
        """Load OBS configuration from JSON file."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
        except FileNotFoundError:
            logger.warning("Config file not found, using defaults")
            self.config = self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config: {e}")
            messagebox.showerror(
                "Config Error",
                f"Invalid configuration file:\n{e}"
            )
            self.config = self._get_default_config()
            
    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration structure.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "connection": {
                "host": "localhost",
                "port": 4455,
                "password": "",
                "auto_connect": True,
                "reconnect_max_delay": 60,
            },
            "scene_mappings": {},
            "default_text_file": "TextInputFiles/webcam_background.txt",
            "unmapped_scene_behaviour": "keep_current",
        }
        
    def _discover_text_files(self) -> None:
        """Discover available text files in TextInputFiles directory."""
        text_files_dir = Path("TextInputFiles")
        
        if not text_files_dir.exists():
            logger.warning("TextInputFiles directory not found")
            self.text_files = []
            return
            
        # Find all .txt files (glob returns relative paths already)
        self.text_files = sorted(
            [str(f).replace("\\", "/") for f in text_files_dir.glob("*.txt")]
        )
        logger.info(f"Found {len(self.text_files)} text files")
        
    def _create_widgets(self) -> None:
        """Create all GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Connection settings section (takes 6 rows: header + 5 fields)
        self._create_connection_section(main_frame, row=current_row)
        current_row += 6
        
        # Scene mappings section (takes 4 rows: header + canvas + button)
        self._create_mappings_section(main_frame, row=current_row)
        current_row += 4
        
        # Behaviour settings section (takes 4 rows: header + 3 fields)
        self._create_behaviour_section(main_frame, row=current_row)
        current_row += 4
        
        # Buttons section
        self._create_buttons_section(main_frame, row=current_row)
        
    def _create_connection_section(
        self,
        parent: ttk.Frame,
        row: int
    ) -> None:
        """Create connection settings section.
        
        Args:
            parent: Parent frame
            row: Grid row position
        """
        # Section label
        section_label = ttk.Label(
            parent,
            text="OBS WebSocket Connection",
            font=("TkDefaultFont", 10, "bold")
        )
        section_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        # Host
        ttk.Label(parent, text="Host:").grid(
            row=row+1, column=0, sticky="w", pady=2
        )
        self.host_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.host_var, width=30).grid(
            row=row+1, column=1, sticky="ew", pady=2
        )
        
        # Port
        ttk.Label(parent, text="Port:").grid(
            row=row+2, column=0, sticky="w", pady=2
        )
        self.port_var = tk.IntVar()
        ttk.Entry(parent, textvariable=self.port_var, width=30).grid(
            row=row+2, column=1, sticky="ew", pady=2
        )
        
        # Password
        ttk.Label(parent, text="Password:").grid(
            row=row+3, column=0, sticky="w", pady=2
        )
        self.password_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.password_var, show="*", width=30).grid(
            row=row+3, column=1, sticky="ew", pady=2
        )
        
        # Auto-connect
        self.auto_connect_var = tk.BooleanVar()
        ttk.Checkbutton(
            parent,
            text="Auto-connect on start",
            variable=self.auto_connect_var
        ).grid(row=row+4, column=0, columnspan=2, sticky="w", pady=2)
        
    def _create_mappings_section(
        self,
        parent: ttk.Frame,
        row: int
    ) -> None:
        """Create scene mappings section.
        
        Args:
            parent: Parent frame
            row: Grid row position
        """
        # Section label
        section_label = ttk.Label(
            parent,
            text="Scene Mappings",
            font=("TkDefaultFont", 10, "bold")
        )
        section_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Mappings frame with scrollbar
        mappings_frame = ttk.Frame(parent)
        mappings_frame.grid(
            row=row+1, column=0, columnspan=2, sticky="ew", pady=5
        )
        
        # Create canvas for scrolling
        canvas = tk.Canvas(mappings_frame, height=200)
        scrollbar = ttk.Scrollbar(
            mappings_frame, orient="vertical", command=canvas.yview
        )
        self.mappings_inner_frame = ttk.Frame(canvas)
        
        self.mappings_inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.mappings_inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Store mapping widgets
        self.mapping_widgets: list[dict[str, Any]] = []
        
        # Add mapping button
        add_btn = ttk.Button(
            parent,
            text="Add Scene Mapping",
            command=self._add_mapping_row
        )
        add_btn.grid(row=row+2, column=0, columnspan=2, sticky="w", pady=5)
        
    def _create_behaviour_section(
        self,
        parent: ttk.Frame,
        row: int
    ) -> None:
        """Create behaviour settings section.
        
        Args:
            parent: Parent frame
            row: Grid row position
        """
        # Section label
        section_label = ttk.Label(
            parent,
            text="Behaviour Settings",
            font=("TkDefaultFont", 10, "bold")
        )
        section_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(15, 5))
        
        # Default text file
        ttk.Label(parent, text="Default Text File:").grid(
            row=row+1, column=0, sticky="w", pady=2
        )
        self.default_file_var = tk.StringVar()
        default_combo = ttk.Combobox(
            parent,
            textvariable=self.default_file_var,
            values=self.text_files,
            state="readonly",
            width=40
        )
        default_combo.grid(row=row+1, column=1, sticky="ew", pady=2)
        
        # Unmapped scene behaviour
        ttk.Label(parent, text="Unmapped Scene:").grid(
            row=row+2, column=0, sticky="w", pady=2
        )
        self.unmapped_behaviour_var = tk.StringVar()
        behaviour_combo = ttk.Combobox(
            parent,
            textvariable=self.unmapped_behaviour_var,
            values=["keep_current", "use_default"],
            state="readonly",
            width=40
        )
        behaviour_combo.grid(row=row+2, column=1, sticky="ew", pady=2)
        
    def _create_buttons_section(
        self,
        parent: ttk.Frame,
        row: int
    ) -> None:
        """Create action buttons section.
        
        Args:
            parent: Parent frame
            row: Grid row position
        """
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(20, 0))
        
        # Save button
        save_btn = ttk.Button(
            button_frame,
            text="Save Settings",
            command=self._save_settings
        )
        save_btn.pack(side="left", padx=5)
        
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.root.destroy
        )
        cancel_btn.pack(side="left", padx=5)
        
    def _add_mapping_row(
        self,
        scene_name: str = "",
        text_file: str = "",
        order_type: str = "random"
    ) -> None:
        """Add a new scene mapping row.
        
        Args:
            scene_name: Initial scene name value
            text_file: Initial text file value
            order_type: Order type ("random" or "fixed")
        """
        row_frame = ttk.Frame(self.mappings_inner_frame)
        row_frame.pack(fill="x", pady=2)
        
        # Scene name entry
        scene_var = tk.StringVar(value=scene_name)
        scene_entry = ttk.Entry(row_frame, textvariable=scene_var, width=20)
        scene_entry.pack(side="left", padx=2)
        
        # Arrow label
        ttk.Label(row_frame, text="→").pack(side="left", padx=5)
        
        # Text file combobox
        file_var = tk.StringVar(value=text_file)
        file_combo = ttk.Combobox(
            row_frame,
            textvariable=file_var,
            values=self.text_files,
            state="readonly",
            width=25
        )
        file_combo.pack(side="left", padx=2)
        
        # Order type combobox
        order_var = tk.StringVar(value=order_type)
        order_combo = ttk.Combobox(
            row_frame,
            textvariable=order_var,
            values=["random", "fixed"],
            state="readonly",
            width=8
        )
        order_combo.pack(side="left", padx=2)
        
        # Remove button
        remove_btn = ttk.Button(
            row_frame,
            text="✕",
            width=3,
            command=lambda: self._remove_mapping_row(row_frame)
        )
        remove_btn.pack(side="left", padx=2)
        
        # Store widget references
        self.mapping_widgets.append({
            "frame": row_frame,
            "scene_var": scene_var,
            "file_var": file_var,
            "order_var": order_var,
        })
        
    def _remove_mapping_row(self, row_frame: ttk.Frame) -> None:
        """Remove a scene mapping row.
        
        Args:
            row_frame: Frame to remove
        """
        # Remove from widget list
        self.mapping_widgets = [
            w for w in self.mapping_widgets if w["frame"] != row_frame
        ]
        
        # Destroy frame
        row_frame.destroy()
        
    def _populate_widgets(self) -> None:
        """Load current configuration values into widgets."""
        # Connection settings
        conn = self.config.get("connection", {})
        self.host_var.set(conn.get("host", "localhost"))
        self.port_var.set(conn.get("port", 4455))
        self.password_var.set(conn.get("password", ""))
        self.auto_connect_var.set(conn.get("auto_connect", True))
        
        # Scene mappings
        mappings = self.config.get("scene_mappings", {})
        for scene_name, mapping_data in mappings.items():
            # Handle both old format (string) and new format (dict)
            if isinstance(mapping_data, str):
                # Old format: just text file path
                text_file = mapping_data
                order_type = "random"  # Default to random for backward compatibility
            else:
                # New format: dict with text_file and order_type
                text_file = mapping_data.get("text_file", "")
                order_type = mapping_data.get("order_type", "random")
            
            self._add_mapping_row(scene_name, text_file, order_type)
            
        # Behaviour settings
        self.default_file_var.set(
            self.config.get(
                "default_text_file",
                "TextInputFiles/webcam_background.txt"
            )
        )
        self.unmapped_behaviour_var.set(
            self.config.get("unmapped_scene_behaviour", "keep_current")
        )
        
    def _save_settings(self) -> None:
        """Save current settings to configuration file."""
        # TODO: Add input validation
        # TODO: Add error handling for file write failures
        
        try:
            # Build configuration dictionary
            new_config = {
                "connection": {
                    "host": self.host_var.get(),
                    "port": self.port_var.get(),
                    "password": self.password_var.get(),
                    "auto_connect": self.auto_connect_var.get(),
                    "reconnect_max_delay": self.config.get(
                        "connection", {}
                    ).get("reconnect_max_delay", 60),
                },
                "scene_mappings": {},
                "default_text_file": self.default_file_var.get(),
                "unmapped_scene_behaviour": self.unmapped_behaviour_var.get(),
            }
            
            # Extract scene mappings from widgets
            for widget_dict in self.mapping_widgets:
                scene_name = widget_dict["scene_var"].get().strip()
                text_file = widget_dict["file_var"].get()
                order_type = widget_dict["order_var"].get()
                
                if scene_name and text_file:
                    new_config["scene_mappings"][scene_name] = {
                        "text_file": text_file,
                        "order_type": order_type
                    }
                    
            # Write to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2)
                
            logger.info(f"Settings saved to {self.config_path}")
            
            messagebox.showinfo(
                "Settings Saved",
                "OBS Scene Monitor settings saved successfully.\n\n"
                "Restart the monitor for changes to take effect."
            )
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save settings:\n{e}"
            )
            
    def run(self) -> None:
        """Start the GUI main loop."""
        logger.info("Starting OBS Monitor Settings GUI")
        self.root.mainloop()


def main() -> None:
    """Entry point for OBS monitor settings GUI."""
    # TODO: Add command-line argument parsing for config path
    settings_gui = OBSMonitorSettings()
    settings_gui.run()


if __name__ == "__main__":
    main()
