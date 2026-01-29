"""OBS Scene Monitor for automatic text file switching.

Monitors OBS Studio scene changes via WebSocket and updates the display
text file accordingly. Supports auto-reconnect with exponential backoff.
"""

import atexit
import json
import signal
import time
from pathlib import Path
from typing import Any

import obsws_python as obs

from logger_setup import setup_logger

logger = setup_logger(__name__)


class OBSSceneMonitor:
    """Monitor OBS scene changes and update display text file."""

    def __init__(self, config_path: str = "config/obs_config.json") -> None:
        """Initialise OBS scene monitor.
        
        Args:
            config_path: Path to OBS configuration file
        """
        self.config_path: Path = Path(config_path)
        self.config: dict[str, Any] = {}
        self.event_client: obs.EventClient | None = None
        self.is_running: bool = False
        self.reconnect_delay: float = 1.0
        self.min_reconnect_delay: float = 1.0
        self.max_reconnect_delay: float = 60.0
        self.current_scene: str | None = None
        
        # Load configuration
        self._load_config()
        
    def on_current_program_scene_changed(self, data: Any) -> None:
        """Handle OBS scene change event.
        
        IMPORTANT: Function name must match pattern on_{snake_case_event_name}
        for obsws-python callback system to work.
        
        Args:
            data: Event data from OBS (as dataclass)
        """
        # Extract scene name from dataclass
        scene_name: str = getattr(data, 'sceneName', getattr(data, 'scene_name', 'Unknown'))
        
        logger.info(f"=== SCENE CHANGE EVENT RECEIVED ===")
        logger.info(f"New scene: {scene_name}")
        
        # Skip if same scene
        if scene_name == self.current_scene:
            logger.info(f"Scene unchanged, skipping")
            return
            
        self.current_scene = scene_name
        logger.info(f"Scene changed from previous to: {scene_name}")
        
        # Look up scene in mappings
        scene_mappings = self.config.get("scene_mappings", {})
        logger.info(f"Checking {len(scene_mappings)} scene mappings")
        
        if scene_name in scene_mappings:
            mapping_data = scene_mappings[scene_name]
            
            # Handle both old format (string) and new format (dict with text_file and order_type)
            if isinstance(mapping_data, str):
                text_file = mapping_data
                order_type = "random"  # Default to random for backward compatibility
            else:
                text_file = mapping_data.get("text_file", "")
                order_type = mapping_data.get("order_type", "random")
            
            logger.info(f"Found mapping: '{scene_name}' -> '{text_file}' (order: {order_type})")
            self._update_text_file(text_file, order_type)
        else:
            logger.info(f"No mapping found for scene: '{scene_name}'")
            # Handle unmapped scene
            behaviour = self.config.get(
                "unmapped_scene_behaviour",
                "keep_current"
            )
            
            if behaviour == "use_default":
                default_file = self.config.get(
                    "default_text_file",
                    "TextInputFiles/webcam_background.txt"
                )
                # Use random order for default file
                self._update_text_file(default_file, "random")
                logger.info(
                    f"Unmapped scene '{scene_name}', "
                    f"using default: {default_file}"
                )
            else:
                logger.info(
                    f"Unmapped scene '{scene_name}', keeping current text"
                )
        
    def _load_config(self) -> None:
        """Load OBS configuration from JSON file."""
        # TODO: Add error handling for missing config file
        # TODO: Add config validation
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
            logger.info(f"Loaded OBS config from {self.config_path}")
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
            
    def _get_connection_params(self) -> dict[str, Any]:
        """Extract connection parameters from config.
        
        Returns:
            Dictionary with host, port, and password
        """
        conn_config = self.config.get("connection", {})
        return {
            "host": conn_config.get("host", "localhost"),
            "port": conn_config.get("port", 4455),
            "password": conn_config.get("password", ""),
        }
        
    def _update_text_file(self, text_file: str, order_type: str = "random") -> None:
        """Write new text file path and order type to config files.
        
        Args:
            text_file: Path to text file to display
            order_type: Order type for text blocks ("random" or "fixed")
        """
        # TODO: Add validation that text file exists
        current_text_path = Path("config/current_text_file.txt")
        order_preference_path = Path("config/obs_order_preference.txt")
        
        try:
            # Write text file path
            with open(current_text_path, "w", encoding="utf-8") as f:
                f.write(text_file)
            
            # Write order preference
            with open(order_preference_path, "w", encoding="utf-8") as f:
                f.write(order_type)
            
            logger.info(f"Updated display text file to: {text_file} (order: {order_type})")
        except IOError as e:
            logger.error(f"Failed to update text file: {e}")
            
    def _connect(self) -> bool:
        """Attempt to connect to OBS WebSocket server.
        
        Returns:
            True if connection successful, False otherwise
        """
        params = self._get_connection_params()
        
        try:
            # Create event client
            self.event_client = obs.EventClient(
                host=params["host"],
                port=params["port"],
                password=params["password"],
            )
            
            # Register callback - MUST be named on_{snake_case_event_name}
            # For CurrentProgramSceneChanged -> on_current_program_scene_changed
            self.event_client.callback.register(self.on_current_program_scene_changed)
            
            logger.info(
                f"Connected to OBS at {params['host']}:{params['port']}"
            )
            logger.info("Registered scene change callback")
            
            # Reset reconnect delay on successful connection
            self.reconnect_delay = self.min_reconnect_delay
            
            return True
            
        except ConnectionRefusedError as e:
            logger.error(
                f"Connection refused by OBS at {params['host']}:{params['port']}. "
                "Make sure OBS Studio is running and WebSocket server is enabled "
                "(Tools > WebSocket Server Settings > Enable WebSocket server)"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to connect to OBS: {e}", exc_info=True)
            return False
            
    def _disconnect(self) -> None:
        """Disconnect from OBS WebSocket server."""
        if self.event_client is not None:
            try:
                self.event_client.disconnect()
                logger.info("Disconnected from OBS")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.event_client = None
                
    def _calculate_reconnect_delay(self) -> float:
        """Calculate next reconnect delay with exponential backoff.
        
        Returns:
            Delay in seconds
        """
        # Get max delay from config
        max_delay = self.config.get("connection", {}).get(
            "reconnect_max_delay",
            self.max_reconnect_delay
        )
        
        # Double the delay
        self.reconnect_delay = min(self.reconnect_delay * 2, max_delay)
        
        return self.reconnect_delay
        
    def start(self) -> None:
        """Start monitoring OBS scene changes."""
        self.is_running = True
        logger.info("Starting OBS scene monitor...")
        
        # Check if auto-connect is enabled
        if not self.config.get("connection", {}).get("auto_connect", True):
            logger.info("Auto-connect disabled, waiting for manual start")
            return
            
        # Main monitoring loop
        while self.is_running:
            if self.event_client is None:
                # Attempt connection
                if self._connect():
                    logger.info("OBS monitor running")
                else:
                    # Calculate backoff delay
                    delay = self._calculate_reconnect_delay()
                    logger.warning(
                        f"Reconnecting in {delay:.1f} seconds..."
                    )
                    time.sleep(delay)
                    continue
                    
            # Keep alive - sleep and check periodically
            try:
                time.sleep(1.0)
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
                break
                
    def stop(self) -> None:
        """Stop monitoring and disconnect."""
        logger.info("Stopping OBS scene monitor...")
        self.is_running = False
        self._disconnect()
        

def main() -> None:
    """Entry point for OBS scene monitor."""
    logger.info("=" * 60)
    logger.info("OBS Scene Monitor Starting")
    logger.info("=" * 60)
    
    # TODO: Add command-line argument parsing for config path
    monitor = OBSSceneMonitor()
    
    # Register cleanup handlers
    def cleanup_handler(signum=None, frame=None):
        """Handle shutdown signals gracefully."""
        if signum is not None:
            logger.info(f"Received signal {signum}, shutting down...")
        monitor.stop()
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup_handler)
    signal.signal(signal.SIGTERM, cleanup_handler)
    
    # Register atexit handler as final fallback
    atexit.register(cleanup_handler)
    
    try:
        monitor.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        monitor.stop()
        logger.info("OBS Scene Monitor stopped")


if __name__ == "__main__":
    main()
