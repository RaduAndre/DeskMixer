"""Serial Monitor Tab - Displays serial communication"""
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from utils.error_handler import log_error
from ui.components import StyledButton, StyledFrame


class SerialMonitorTab:
    """Serial monitor tab UI"""

    def __init__(self, parent, serial_handler=None):
        """
        Initialize serial monitor tab

        Args:
            parent: Parent widget
            serial_handler: Serial handler instance
        """
        self.serial_handler = serial_handler
        self.frame = StyledFrame(parent, bg="#1e1e1e")
        self.auto_scroll = True

        # UI components
        self.monitor = None
        self.input_var = None
        self.auto_scroll_var = None

        self._create_ui()
        self._register_callbacks()

    def _create_ui(self):
        """Create the serial monitor UI"""
        try:
            # Main container
            main_container = StyledFrame(self.frame, bg="#1e1e1e")
            main_container.pack(fill="both", expand=True, padx=10, pady=10)

            # Top controls
            self._create_controls(main_container)

            # Monitor text area
            self._create_monitor(main_container)

            # Input frame
            self._create_input(main_container)

        except Exception as e:
            log_error(e, "Failed to create serial monitor UI")

    def _create_controls(self, parent):
        """Create control buttons and checkboxes"""
        controls_frame = StyledFrame(parent)
        controls_frame.pack(fill="x", padx=5, pady=5)

        # Auto-scroll checkbox
        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_scroll_cb = ttk.Checkbutton(
            controls_frame,
            text="Auto-scroll",
            variable=self.auto_scroll_var,
            style='Switch.TCheckbutton'
        )
        auto_scroll_cb.pack(side="left", padx=5)

        # Clear button
        clear_btn = StyledButton(
            controls_frame,
            text="Clear Monitor",
            command=self._clear_monitor,
            style="primary"
        )
        clear_btn.pack(side="left", padx=5)

    def _create_monitor(self, parent):
        """Create monitor text area"""
        self.monitor = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            bg="#2d2d2d",
            fg="#00ff00",
            font=("Consolas", 10),
            height=20
        )
        self.monitor.pack(fill="both", expand=True, pady=5)

    def _create_input(self, parent):
        """Create input field and send button"""
        input_frame = StyledFrame(parent)
        input_frame.pack(fill="x", padx=5, pady=(0, 5))

        self.input_var = tk.StringVar()
        input_entry = tk.Entry(
            input_frame,
            textvariable=self.input_var,
            bg="#2d2d2d",
            fg="white",
            insertbackground="white"
        )
        input_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        send_btn = StyledButton(
            input_frame,
            text="Send",
            command=self._send_data,
            style="primary"
        )
        send_btn.pack(side="right")

        # Bind Enter key to send
        input_entry.bind("<Return>", lambda e: self._send_data())

    def _register_callbacks(self):
        """Register for serial data callbacks"""
        try:
            if self.serial_handler and hasattr(self.serial_handler, "add_callback"):
                self.serial_handler.add_callback(self._on_serial_data)
        except Exception as e:
            log_error(e, "Failed to add serial monitor callback")

    def _on_serial_data(self, data):
        """
        Handle incoming serial data

        Args:
            data: Serial data (bytes or string)
        """
        try:
            if data is None:
                return

            # Convert to string
            if isinstance(data, (bytes, bytearray)):
                try:
                    text = data.decode('utf-8', errors='ignore')
                except Exception:
                    text = str(data)
            else:
                text = str(data)

            # Display each line with timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            for line in text.replace('\r', '').splitlines():
                if not line.strip():
                    continue
                entry = f"[{timestamp}] {line}\n"
                try:
                    self.monitor.insert(tk.END, entry)
                except Exception:
                    pass

            # Auto-scroll if enabled
            if self.auto_scroll_var and self.auto_scroll_var.get():
                try:
                    self.monitor.see(tk.END)
                except Exception:
                    pass

        except Exception as e:
            log_error(e, "Error in serial monitor callback")

    def _send_data(self):
        """Send data through serial connection"""
        try:
            payload = self.input_var.get().strip()
            if not payload:
                return

            if self.serial_handler and hasattr(self.serial_handler, "write"):
                data = (payload + "\n").encode('utf-8') if isinstance(payload, str) else payload
                self.serial_handler.write(data)

            # Show sent message in monitor
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.monitor.insert(tk.END, f"[{timestamp}] >> {payload}\n")

            if self.auto_scroll_var and self.auto_scroll_var.get():
                self.monitor.see(tk.END)

            # Clear input
            self.input_var.set("")

        except Exception as e:
            log_error(e, "Error sending serial data")

    def _clear_monitor(self):
        """Clear the monitor text area"""
        self.monitor.delete(1.0, tk.END)
