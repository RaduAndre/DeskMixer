# ui/config_serial_section.py
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial.tools.list_ports as serial_list_ports
except Exception:
    serial_list_ports = None

from utils.error_handler import log_error
from utils.system_startup import set_startup, check_startup_status


class ConfigSerialSection:
    """Handles the Serial Port Configuration UI and logic."""

    def __init__(self, parent_frame, serial_handler, config_manager):
        self.serial_handler = serial_handler
        self.config_manager = config_manager

        # UI Variables
        self.com_port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value="9600")

        # Settings variables
        self.start_in_tray = tk.BooleanVar(value=self.config_manager.get_start_in_tray(default=False))
        self.start_on_windows_start = tk.BooleanVar(value=check_startup_status())

        self.serial_status_label = None
        self.connect_btn = None
        self.com_combo = None

        self._create_ui(parent_frame)
        self._load_initial_values()

        # Register callbacks for disconnect/reconnect events
        if self.serial_handler:
            self.serial_handler.add_disconnect_callback(self._on_device_disconnected)
            self.serial_handler.add_reconnect_callback(self._on_device_reconnected)

    def _create_ui(self, parent):
        """Create the serial port configuration section UI."""
        try:
            serial_frame = tk.LabelFrame(
                parent,
                text="Serial Port Configuration",
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
            controls.grid_columnconfigure(1, weight=1)
            controls.grid_columnconfigure(3, weight=1)

            # Row 0: COM Port and Baud Rate
            tk.Label(
                controls,
                text="COM Port:",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 9)
            ).grid(row=0, column=0, padx=5, pady=5, sticky="w")

            com_ports = [port.device for port in (serial_list_ports.comports() if serial_list_ports else [])]

            self.com_combo = ttk.Combobox(
                controls,
                textvariable=self.com_port_var,
                values=com_ports,
                state="readonly",
                width=15
            )
            self.com_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            if com_ports:
                self.com_combo.current(0)

            # Bind the dropdown click event to refresh ports
            self.com_combo.bind('<Button-1>', self._on_dropdown_click)

            tk.Label(
                controls,
                text="Baud Rate:",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 9)
            ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

            baud_combo = ttk.Combobox(
                controls,
                textvariable=self.baud_var,
                values=["9600", "19200", "38400", "57600", "115200"],
                state="readonly",
                width=10
            )
            baud_combo.grid(row=0, column=3, padx=5, pady=5, sticky="w")

            # Row 1: Status and buttons
            status_frame = tk.Frame(controls, bg="#2d2d2d")
            status_frame.grid(row=1, column=0, columnspan=4, sticky="ew", pady=5)

            self.serial_status_label = tk.Label(
                status_frame,
                text="● Disconnected",
                bg="#2d2d2d",
                fg="#ff0000",
                font=("Arial", 9, "bold")
            )
            self.serial_status_label.pack(side="left", padx=10)

            self.connect_btn = tk.Button(
                status_frame,
                text="Connect",
                command=self._toggle_serial,
                bg="#404040",
                fg="white",
                font=("Arial", 9, "bold"),
                relief="flat",
                padx=15,
                pady=5,
                cursor="hand2"
            )
            self.connect_btn.pack(side="left", padx=5)

            # Refresh button removed - auto-refresh on dropdown click instead

            # Row 2: Settings checkboxes
            settings_frame = tk.Frame(controls, bg="#2d2d2d")
            settings_frame.grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

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
            tray_check.pack(side="left", padx=(10, 15))

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
            startup_check.pack(side="left", padx=(0, 10))

            self.frame = serial_frame

        except Exception as e:
            log_error(e, "Error creating serial section")

    def _on_dropdown_click(self, event):
        """Auto-refresh ports when dropdown is clicked."""
        try:
            # Get current selection to preserve it if possible
            current_port = self.com_port_var.get()

            # Refresh the port list
            com_ports = [port.device for port in (serial_list_ports.comports() if serial_list_ports else [])]
            self.com_combo['values'] = com_ports

            # Try to keep the current selection if it's still available
            if current_port in com_ports:
                self.com_port_var.set(current_port)
            elif com_ports:
                self.com_combo.current(0)

        except Exception as e:
            log_error(e, "Error auto-refreshing ports on dropdown click")

    def _on_device_disconnected(self):
        """Called when device is physically disconnected"""
        try:
            # Update UI to show disconnected state
            if self.serial_status_label:
                self.serial_status_label.config(
                    text="● Disconnected (Reconnecting...)",
                    fg="#ffaa00"
                )
            if self.connect_btn:
                self.connect_btn.config(text="Connect", state="disabled")

        except Exception as e:
            log_error(e, "Error updating UI on disconnect")

    def _on_device_reconnected(self):
        """Called when device successfully reconnects"""
        try:
            # Update UI to show connected state
            if self.serial_status_label:
                self.serial_status_label.config(
                    text="● Connected (Reconnected)",
                    fg="#00ff00"
                )
            if self.connect_btn:
                self.connect_btn.config(text="Disconnect", state="normal")

            # Show a brief notification
            self.serial_status_label.after(3000, lambda: self.serial_status_label.config(
                text="● Connected"
            ))

        except Exception as e:
            log_error(e, "Error updating UI on reconnect")

    def _handle_tray_setting_change(self):
        """Saves the 'Start Hidden (in Tray)' checkbox state to the config."""
        self.config_manager.set_start_in_tray(self.start_in_tray.get())
        self.config_manager.save_config_if_changed()

    def _handle_startup_setting_change(self):
        """Handles changes to the 'Start on Windows Startup' checkbox."""
        set_startup(self.start_on_windows_start.get())

    def _load_initial_values(self):
        """Load last connected port/baud from config."""
        try:
            config = self.config_manager.load_config()
            last_port = config.get('last_connected_port')
            last_baud = config.get('last_connected_baud', "9600")
            if last_port:
                self.com_port_var.set(last_port)
                self.baud_var.set(last_baud)

        except Exception as e:
            log_error(e, "Error loading serial config")

    def _refresh_ports(self):
        """Refresh available COM ports"""
        try:
            com_ports = [port.device for port in (serial_list_ports.comports() if serial_list_ports else [])]
            self.com_combo['values'] = com_ports
            if com_ports:
                self.com_combo.current(0)

        except Exception as e:
            log_error(e, "Error refreshing ports")

    def auto_connect(self):
        """Attempt to automatically connect to the last used serial port."""
        try:
            config = self.config_manager.load_config()
            last_port = config.get('last_connected_port', None)
            last_baud = config.get('last_connected_baud', "9600")

            if last_port:
                # Ensure the port is still available
                com_ports = [port.device for port in (serial_list_ports.comports() if serial_list_ports else [])]
                if last_port in com_ports:
                    self.com_port_var.set(last_port)
                    self.baud_var.set(last_baud)
                    self._toggle_serial(auto=True)  # Attempt connection
                else:
                    log_error(Exception(f"Last connected port {last_port} not found."), "Auto-connect failed.")
        except Exception as e:
            log_error(e, "Error during auto-connect attempt.")

    def _toggle_serial(self, auto=False):
        """Toggle serial connection"""
        try:
            if not self.serial_handler.is_connected():
                port = self.com_port_var.get()
                baud = int(self.baud_var.get())

                if not port:
                    if not auto:
                        messagebox.showerror("Error", "Please select a COM port")
                    return

                success = self.serial_handler.connect(port, baud)

                if success:
                    self.serial_status_label.config(
                        text="● Connected",
                        fg="#00ff00"
                    )
                    self.connect_btn.config(text="Disconnect")
                    if not auto:
                        messagebox.showinfo("Success", f"Connected to {port}")

                    # Save the connected port
                    self.config_manager.set_last_connected_port(port, baud)
                    self.config_manager.save_config_if_changed()
                else:
                    self.serial_status_label.config(
                        text="● Disconnected",
                        fg="#ff0000"
                    )
                    self.connect_btn.config(text="Connect")
                    if not auto:
                        messagebox.showerror("Error", "Failed to connect to serial port")
            else:
                # User manually disconnected - stop auto-reconnection
                self.serial_handler.stop_reconnect = True
                self.serial_handler.disconnect()

                self.serial_status_label.config(
                    text="● Disconnected",
                    fg="#ff0000"
                )
                self.connect_btn.config(text="Connect", state="normal")

                # When disconnecting manually, clear the saved port.
                self.config_manager.set_last_connected_port(None, None)
                self.config_manager.save_config_if_changed()

        except Exception as e:
            messagebox.showerror("Error", f"Error toggling serial connection: {str(e)}")
            log_error(e, "Error toggling serial connection")