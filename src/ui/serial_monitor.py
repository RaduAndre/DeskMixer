import tkinter as tk
from tkinter import ttk, scrolledtext
from utils.error_handler import log_error
from datetime import datetime

class SerialMonitor:
    """Serial monitor tab UI"""

    def __init__(self, parent, serial_handler=None):
        self.serial_handler = serial_handler
        self.frame = tk.Frame(parent, bg="#1e1e1e")
        self.auto_scroll = True
        self._create_ui()
        # Register for incoming serial data if handler available
        try:
            if self.serial_handler and hasattr(self.serial_handler, "add_callback"):
                self.serial_handler.add_callback(self._on_serial_data)
        except Exception as e:
            log_error(e, "Failed to add serial monitor callback")

    def _create_ui(self):
        """Create the serial monitor UI"""
        try:
            # Main container
            main_container = tk.Frame(self.frame, bg="#1e1e1e")
            main_container.pack(fill="both", expand=True, padx=10, pady=10)

            # Top controls
            controls_frame = tk.Frame(main_container, bg="#2d2d2d")
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
            clear_btn = tk.Button(
                controls_frame,
                text="Clear Monitor",
                command=self._clear_monitor,
                bg="#404040",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=10,
                pady=5,
                cursor="hand2"
            )
            clear_btn.pack(side="left", padx=5)

            # Monitor text area
            self.monitor = scrolledtext.ScrolledText(
                main_container,
                wrap=tk.WORD,
                bg="#2d2d2d",
                fg="#00ff00",
                font=("Consolas", 10),
                height=20
            )
            self.monitor.pack(fill="both", expand=True, pady=5)

            # Input frame
            input_frame = tk.Frame(main_container, bg="#2d2d2d")
            input_frame.pack(fill="x", padx=5, pady=(0,5))

            self.input_var = tk.StringVar()
            input_entry = tk.Entry(input_frame, textvariable=self.input_var, bg="#2d2d2d", fg="white", insertbackground="white")
            input_entry.pack(side="left", fill="x", expand=True, padx=(0,5))

            send_btn = tk.Button(
                input_frame,
                text="Send",
                command=self._send_data,
                bg="#404040",
                fg="white",
                relief="flat",
                padx=10,
                pady=4,
                cursor="hand2"
            )
            send_btn.pack(side="right")

        except Exception as e:
            log_error(e, "Failed to create serial monitor UI")

    def _on_serial_data(self, data):
        """Handle incoming serial data"""
        try:
            # Accept bytes or string
            if data is None:
                return
            if isinstance(data, (bytes, bytearray)):
                try:
                    text = data.decode('utf-8', errors='ignore')
                except Exception:
                    text = str(data)
            else:
                text = str(data)

            # Some handlers may send long multi-line payloads; display each line
            timestamp = datetime.now().strftime("%H:%M:%S")
            for line in text.replace('\r', '').splitlines():
                if not line.strip():
                    continue
                entry = f"[{timestamp}] {line}\n"
                try:
                    self.monitor.insert(tk.END, entry)
                except Exception:
                    # If insert fails for some reason, skip
                    pass

            if getattr(self, "auto_scroll_var", None) and self.auto_scroll_var.get():
                try:
                    self.monitor.see(tk.END)
                except:
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
                self.serial_handler.write((payload + "\n").encode('utf-8') if isinstance(payload, str) else payload)
            # show sent in monitor
            ts = datetime.now().strftime("%H:%M:%S")
            self.monitor.insert(tk.END, f"[{ts}] >> {payload}\n")
            if getattr(self, "auto_scroll_var", None) and self.auto_scroll_var.get():
                self.monitor.see(tk.END)

        except Exception as e:
            log_error(e, "Error sending serial data")

    def _clear_monitor(self):
        """Clear the monitor text area"""
        self.monitor.delete(1.0, tk.END)