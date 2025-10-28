import tkinter as tk
from tkinter import ttk
import os
import subprocess

from utils.error_handler import log_error
from utils.system_startup import set_startup, check_startup_status


class ConfigSerialSection:
    """Handles the Serial Port Configuration UI with automatic connection."""

    def __init__(self, parent_frame, serial_handler, config_manager):
        self.serial_handler = serial_handler
        self.config_manager = config_manager

        # Settings variables
        self.start_in_tray = tk.BooleanVar(value=self.config_manager.get_start_in_tray(default=False))
        self.start_on_windows_start = tk.BooleanVar(value=check_startup_status())

        self.serial_status_label = None
        self.serial_details_label = None

        self._create_ui(parent_frame)

        # Register callbacks for status updates
        if self.serial_handler:
            self.serial_handler.add_status_callback(self._on_status_change)

    def _create_ui(self, parent):
        """Create the serial port configuration section UI."""
        try:
            serial_frame = tk.LabelFrame(
                parent,
                text="General configuration",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=10
            )

            # Use grid layout for better control inside the labelframe
            controls = tk.Frame(serial_frame, bg="#2d2d2d")
            controls.grid(row=0, column=0, sticky="ew")

            # Configure grid columns for controls
            controls.grid_columnconfigure(0, weight=1)

            # Row 0: Connection Status
            status_frame = tk.Frame(controls, bg="#2d2d2d")
            status_frame.grid(row=0, column=0, sticky="ew", pady=5)

            tk.Label(
                status_frame,
                text="Connection Status:",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 9, "bold")
            ).pack(side="left", padx=(0, 10))

            self.serial_status_label = tk.Label(
                status_frame,
                text="● Disconnected",
                bg="#2d2d2d",
                fg="#ff0000",
                font=("Arial", 9, "bold")
            )
            self.serial_status_label.pack(side="left", padx=5)

            # Row 1: Connection Details (port and baud)
            self.serial_details_label = tk.Label(
                controls,
                text="No device connected",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 8)
            )
           # self.serial_details_label.grid(row=1, column=0, sticky="w", pady=(0, 10))

            # Row 2: Settings checkboxes
            settings_frame = tk.Frame(controls, bg="#2d2d2d")
            settings_frame.grid(row=2, column=0, sticky="w", pady=(10, 0))

            # Checkbox for "Start Hidden (in Tray)"
            tray_check = tk.Checkbutton(
                settings_frame,
                text="Start Hidden (in Tray)",
                variable=self.start_in_tray,
                bg="#2d2d2d",
                fg="white",
                selectcolor="#2d2d2d",
                command=self._handle_tray_setting_change
            )
            tray_check.pack(side="left", padx=(0, 15))

            # Checkbox for "Start on Windows Startup"
            startup_check = tk.Checkbutton(
                settings_frame,
                text="Start on Windows Startup",
                variable=self.start_on_windows_start,
                bg="#2d2d2d",
                fg="white",
                selectcolor="#2d2d2d",
                command=self._handle_startup_setting_change
            )
            startup_check.pack(side="left", padx=(0, 15))

            # Button to open config folder
            open_folder_btn = tk.Button(
                settings_frame,
                text="Open Config Folder",
                command=self._open_config_folder,
                bg="#3d3d3d",
                fg="white",
                relief="flat",
                cursor="hand2",
                font=("Arial", 8)
            )
            open_folder_btn.pack(side="left", padx=(0, 10))

            self.frame = serial_frame

        except Exception as e:
            log_error(e, "Error creating serial section")

    def _open_config_folder(self):
        """Open the configuration folder in file explorer"""
        try:
            # Get the config folder path from config_manager
            config_folder = self.config_manager.config_dir

            if os.path.exists(config_folder):
                # Open the folder in file explorer
                if os.name == 'nt':  # Windows
                    os.startfile(config_folder)
                elif os.name == 'posix':  # macOS or Linux
                    subprocess.run(['open', config_folder] if sys.platform == 'darwin' else ['xdg-open', config_folder])
                else:
                    log_error(Exception("Unsupported OS"), "Cannot open folder")
            else:
                log_error(Exception("Folder does not exist"), f"Config folder not found: {config_folder}")
        except Exception as e:
            log_error(e, "Error opening config folder")

    def _on_status_change(self, status, message):
        """Called when connection status changes"""
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
                    "details": self._get_connection_details()
                },
                "reconnecting": {
                    "text": "● Reconnecting...",
                    "color": "#ffaa00",
                    "details": message
                },
                "reconnected": {
                    "text": "● Reconnected",
                    "color": "#00ff00",
                    "details": self._get_connection_details()
                }
            }

            config = status_config.get(status, status_config["disconnected"])

            if self.serial_status_label:
                self.serial_status_label.config(
                    text=config["text"],
                    fg=config["color"]
                )

            if self.serial_details_label:
                self.serial_details_label.config(
                    text=config["details"]
                )

            # For reconnected status, show temporary message then revert to "Connected"
            if status == "reconnected":
                self.serial_status_label.after(3000, lambda: self._on_status_change("connected", message))

        except Exception as e:
            log_error(e, "Error updating UI on status change")

    def _get_connection_details(self):
        """Get current connection details for display"""
        try:
            if self.serial_handler and self.serial_handler.is_connected():
                port = self.serial_handler.port.replace('\\\\.\\', '') if self.serial_handler.port else "Unknown"
                baud = self.serial_handler.baud_rate
                return f"Connected to {port} at {baud} baud"
            return "No device connected"
        except Exception as e:
            log_error(e, "Error getting connection details")
            return "Connection details unavailable"

    def _handle_tray_setting_change(self):
        """Saves the 'Start Hidden (in Tray)' checkbox state to the config."""
        self.config_manager.set_start_in_tray(self.start_in_tray.get())
        self.config_manager.save_config_if_changed()

    def _handle_startup_setting_change(self):
        """Handles changes to the 'Start on Windows Startup' checkbox."""
        set_startup(self.start_on_windows_start.get())

    def auto_connect(self):
        """Attempt to automatically connect to device with handshake."""
        try:
            if self.serial_handler:
                # Start connection in a separate thread to avoid blocking UI
                import threading
                connection_thread = threading.Thread(
                    target=self.serial_handler.auto_connect,
                    daemon=True
                )
                connection_thread.start()
        except Exception as e:
            log_error(e, "Error during auto-connect attempt.")