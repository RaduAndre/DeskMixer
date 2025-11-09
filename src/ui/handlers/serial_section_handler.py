"""Serial Section Handler - Business logic for serial configuration"""
import os
import sys
import subprocess
import threading
from utils.error_handler import log_error
from utils.system_startup import set_startup, check_startup_status


class SerialSectionHandler:
    """Handles serial configuration business logic"""

    def __init__(self, serial_handler, config_manager):
        """
        Initialize serial section handler

        Args:
            serial_handler: Serial handler instance
            config_manager: Config manager instance
        """
        self.serial_handler = serial_handler
        self.config_manager = config_manager
        self.ui_callback = None

    def set_ui_callback(self, callback):
        """
        Set callback for UI updates

        Args:
            callback: Function to call for UI updates
        """
        self.ui_callback = callback

    def register_status_callback(self):
        """Register for serial status updates"""
        if self.serial_handler:
            self.serial_handler.add_status_callback(self._on_status_change)

    def get_start_in_tray(self):
        """Get start in tray setting"""
        return self.config_manager.get_start_in_tray(default=False)

    def get_start_on_windows_start(self):
        """Get start on Windows startup setting"""
        return check_startup_status()

    def set_start_in_tray(self, value):
        """
        Save start in tray setting

        Args:
            value: Boolean value for start in tray
        """
        self.config_manager.set_start_in_tray(value)
        self.config_manager.save_config_if_changed()

    def set_start_on_windows_start(self, value):
        """
        Set start on Windows startup

        Args:
            value: Boolean value for startup
        """
        set_startup(value)

    def open_config_folder(self):
        """Open the configuration folder in file explorer"""
        try:
            config_folder = self.config_manager.config_dir

            if os.path.exists(config_folder):
                if os.name == 'nt':  # Windows
                    os.startfile(config_folder)
                elif os.name == 'posix':  # macOS or Linux
                    if sys.platform == 'darwin':
                        subprocess.run(['open', config_folder])
                    else:
                        subprocess.run(['xdg-open', config_folder])
                else:
                    log_error(Exception("Unsupported OS"), "Cannot open folder")
            else:
                log_error(
                    Exception("Folder does not exist"),
                    f"Config folder not found: {config_folder}"
                )
        except Exception as e:
            log_error(e, "Error opening config folder")

    def auto_connect(self):
        """Attempt to automatically connect to device with handshake"""
        try:
            if self.serial_handler:
                # Start connection in a separate thread to avoid blocking UI
                connection_thread = threading.Thread(
                    target=self.serial_handler.auto_connect,
                    daemon=True
                )
                connection_thread.start()
        except Exception as e:
            log_error(e, "Error during auto-connect attempt")

    def get_connection_details(self):
        """
        Get current connection details for display

        Returns:
            String with connection details
        """
        try:
            if self.serial_handler and self.serial_handler.is_connected():
                port = self.serial_handler.port
                if port:
                    port = port.replace('\\\\.\\', '')
                else:
                    port = "Unknown"
                baud = self.serial_handler.baud_rate
                return f"Connected to {port} at {baud} baud"
            return "No device connected"
        except Exception as e:
            log_error(e, "Error getting connection details")
            return "Connection details unavailable"

    def _on_status_change(self, status, message):
        """
        Called when connection status changes

        Args:
            status: Connection status string
            message: Status message
        """
        try:
            status_config = {
                "disconnected": {
                    "text": "● Disconnected",
                    "color": "#ff0000",
                    "details": "No device connected"
                },
                "connecting": {
                    "text": "● Connecting...",
                    "color": "#ffaa00",
                    "details": message
                },
                "connected": {
                    "text": "● Connected",
                    "color": "#00ff00",
                    "details": self.get_connection_details()
                },
                "reconnecting": {
                    "text": "● Reconnecting...",
                    "color": "#ffaa00",
                    "details": message
                },
                "reconnected": {
                    "text": "● Reconnected",
                    "color": "#00ff00",
                    "details": self.get_connection_details()
                }
            }

            config = status_config.get(status, status_config["disconnected"])

            # Call UI callback with status information
            if self.ui_callback:
                self.ui_callback(status, config)

        except Exception as e:
            log_error(e, "Error handling status change")
