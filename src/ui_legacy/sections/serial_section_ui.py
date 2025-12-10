"""Serial Section UI - Visual components for serial configuration"""
import tkinter as tk
from utils.error_handler import log_error
from ui.components import StyledLabelFrame, StyledFrame, StyledButton


class SerialSectionUI:
    """Handles the Serial Port Configuration UI"""

    def __init__(self, parent, handler):
        """
        Initialize serial section UI

        Args:
            parent: Parent widget
            handler: SerialSectionHandler instance
        """
        self.handler = handler
        self.frame = None

        # UI components
        self.serial_status_label = None
        self.serial_details_label = None
        self.start_in_tray = None
        self.start_on_windows_start = None

        self._create_ui(parent)
        self._register_callbacks()

    def _create_ui(self, parent):
        """Create the serial port configuration section UI"""
        try:
            # Main frame
            serial_frame = StyledLabelFrame(
                parent,
                text="General configuration"
            )

            # Controls container
            controls = StyledFrame(serial_frame)
            controls.grid(row=0, column=0, sticky="ew")
            controls.grid_columnconfigure(0, weight=1)

            # Create sections
            self._create_status_display(controls)
            self._create_settings_checkboxes(controls)

            self.frame = serial_frame

        except Exception as e:
            log_error(e, "Error creating serial section UI")

    def _create_status_display(self, parent):
        """Create connection status display"""
        status_frame = StyledFrame(parent)
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

        # Details label (can be shown if needed)
        self.serial_details_label = tk.Label(
            parent,
            text="No device connected",
            bg="#2d2d2d",
            fg="#888888",
            font=("Arial", 8)
        )
        # Not gridded by default (line 79 was commented in original)

    def _create_settings_checkboxes(self, parent):
        """Create settings checkboxes and buttons"""
        settings_frame = StyledFrame(parent)
        settings_frame.grid(row=2, column=0, sticky="w", pady=(10, 0))

        # Start in tray checkbox
        self.start_in_tray = tk.BooleanVar(
            value=self.handler.get_start_in_tray()
        )
        tray_check = tk.Checkbutton(
            settings_frame,
            text="Start Hidden (in Tray)",
            variable=self.start_in_tray,
            bg="#2d2d2d",
            fg="white",
            selectcolor="#2d2d2d",
            command=self._on_tray_setting_change
        )
        tray_check.pack(side="left", padx=(0, 15))

        # Start on Windows startup checkbox
        self.start_on_windows_start = tk.BooleanVar(
            value=self.handler.get_start_on_windows_start()
        )
        startup_check = tk.Checkbutton(
            settings_frame,
            text="Start on Windows Startup",
            variable=self.start_on_windows_start,
            bg="#2d2d2d",
            fg="white",
            selectcolor="#2d2d2d",
            command=self._on_startup_setting_change
        )
        startup_check.pack(side="left", padx=(0, 15))

        # Open config folder button
        open_folder_btn = tk.Button(
            settings_frame,
            text="Open Config Folder",
            command=self.handler.open_config_folder,
            bg="#3d3d3d",
            fg="white",
            relief="flat",
            cursor="hand2",
            font=("Arial", 8)
        )
        open_folder_btn.pack(side="left", padx=(0, 10))

    def _register_callbacks(self):
        """Register callbacks with handler"""
        self.handler.set_ui_callback(self._update_status_display)
        self.handler.register_status_callback()

    def _update_status_display(self, status, config):
        """
        Update status display

        Args:
            status: Status string
            config: Dictionary with text, color, and details
        """
        try:
            if self.serial_status_label:
                self.serial_status_label.config(
                    text=config["text"],
                    fg=config["color"]
                )

            if self.serial_details_label:
                self.serial_details_label.config(
                    text=config["details"]
                )

            # For reconnected status, show temporary message then revert
            if status == "reconnected":
                self.serial_status_label.after(
                    3000,
                    lambda: self._update_status_display(
                        "connected",
                        {
                            "text": "● Connected",
                            "color": "#00ff00",
                            "details": self.handler.get_connection_details()
                        }
                    )
                )

        except Exception as e:
            log_error(e, "Error updating status display")

    def _on_tray_setting_change(self):
        """Handle tray setting change"""
        self.handler.set_start_in_tray(self.start_in_tray.get())

    def _on_startup_setting_change(self):
        """Handle startup setting change"""
        self.handler.set_start_on_windows_start(self.start_on_windows_start.get())

    def auto_connect(self):
        """Trigger auto-connect"""
        self.handler.auto_connect()
