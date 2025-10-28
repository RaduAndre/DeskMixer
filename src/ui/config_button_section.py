# ui/config_button_section.py
import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import threading
from utils.error_handler import log_error


class ConfigButtonSection:
    """Handles the Button Bindings UI and logic."""

    def __init__(self, parent_frame, audio_manager, config_manager, common_helpers, serial_handler=None):
        self.audio_manager = audio_manager
        self.config_manager = config_manager
        self.helpers = common_helpers
        self.serial_handler = serial_handler
        self.button_binding_rows = {}  # Store rows by button name
        self.device_button_count = 0  # Track device configuration

        self.button_canvas = None
        self.button_container = None

        # Setup event loop for async operations
        self._setup_async_loop()

        self._create_ui(parent_frame)

        # Register for configuration updates if serial_handler is provided
        if self.serial_handler:
            self.serial_handler.add_config_callback(self._on_device_config)

    def _on_device_config(self, slider_count, button_count):
        """Handle device configuration updates - automatically create/remove button binding rows"""
        try:
            self.device_button_count = button_count
            print(f"Device config: {button_count} buttons, creating/updating binding rows")
            self._synchronize_button_bindings(button_count)
        except Exception as e:
            log_error(e, "Error creating button bindings from device config")

    def _synchronize_button_bindings(self, device_button_count):
        """Synchronize UI with device configuration - create missing or remove extra rows"""
        try:
            # Get current config bindings
            config = self.config_manager.load_config()
            config_bindings = config.get('button_bindings', {})

            # Find which buttons exist in config
            config_buttons = set()
            for button_name in config_bindings.keys():
                if button_name.startswith('b') and button_name[1:].isdigit():
                    config_buttons.add(int(button_name[1:]))

            print(f"Config has buttons: {sorted(config_buttons)}")
            print(f"Device has buttons: {list(range(1, device_button_count + 1))}")

            # Create set of required buttons (union of config and device)
            required_buttons = set(range(1, device_button_count + 1)).union(config_buttons)
            print(f"Required buttons: {sorted(required_buttons)}")

            # Remove UI rows for buttons that are not in required_buttons
            rows_to_remove = []
            for button_name, row_data in self.button_binding_rows.items():
                if button_name.startswith('b'):
                    button_num = int(button_name[1:])
                    if button_num not in required_buttons:
                        rows_to_remove.append(button_name)

            for button_name in rows_to_remove:
                row_data = self.button_binding_rows[button_name]
                row_data['frame'].destroy()
                del self.button_binding_rows[button_name]
                print(f"Removed UI row for {button_name} (not in device or config)")

            # Create UI rows for missing buttons
            for button_num in sorted(required_buttons):
                button_name = f"b{button_num}"
                display_name = f"Button {button_num}"

                # Skip if row already exists
                if button_name in self.button_binding_rows:
                    continue

                # Check if binding exists in config
                config = self.config_manager.load_config()
                button_bindings = config.get('button_bindings', {})
                binding_data = button_bindings.get(button_name, {})

                if isinstance(binding_data, dict):
                    action = binding_data.get('action', '')
                    target = binding_data.get('target', '')
                    keybind = binding_data.get('keybind', '')
                    app_path = binding_data.get('app_path', '')
                    output_mode = binding_data.get('output_mode', 'cycle')
                    output_device = binding_data.get('output_device', '')
                else:
                    action = binding_data
                    target = ''
                    keybind = ''
                    app_path = ''
                    output_mode = 'cycle'
                    output_device = ''

                # Determine if this is auto-created (not in config but in device)
                is_auto = (button_num <= device_button_count and button_num not in config_buttons)

                # Create the row
                self._add_button_binding_row(
                    button_name=button_name,
                    display_name=display_name,
                    action=action,
                    target=target,
                    keybind=keybind,
                    app_path=app_path,
                    output_mode=output_mode,
                    output_device=output_device,
                    is_auto=is_auto
                )

                if is_auto:
                    print(f"Auto-created UI row for {button_name}")
                else:
                    print(f"Created UI row for {button_name} from config")

            # Update status label
            if self.status_label:
                visible_count = len([name for name in self.button_binding_rows.keys() if name.startswith('b')])
                self.status_label.config(
                    text=f"Showing {visible_count} button bindings ({device_button_count} from device)")

        except Exception as e:
            log_error(e, "Error synchronizing button bindings")

    def _setup_async_loop(self):
        """Setup asyncio event loop for async operations"""
        try:
            # Try to get existing event loop
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            # Create new event loop if none exists
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    def _run_async(self, coro):
        """Run an async coroutine in a thread-safe manner"""

        def run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(coro)
                loop.close()
            except Exception as e:
                log_error(e, "Error running async operation")

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

    def _create_ui(self, parent):
        """Create button bindings section"""
        try:
            button_frame = tk.LabelFrame(
                parent,
                text="Button Bindings - Actions",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=10
            )
            button_frame.grid_rowconfigure(1, weight=1)
            button_frame.grid_columnconfigure(0, weight=1)

            help_text = tk.Label(
                button_frame,
                text="Bind the preffered actions to the button of your liking",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 8),
                wraplength=850,
                justify="left"
            )
            help_text.grid(row=0, column=0, sticky="ew", pady=(0, 5))

            canvas_frame = tk.Frame(button_frame, bg="#2d2d2d")
            canvas_frame.grid(row=1, column=0, sticky="nsew")
            canvas_frame.grid_rowconfigure(0, weight=1)
            canvas_frame.grid_columnconfigure(0, weight=1)

            self.button_canvas = tk.Canvas(
                canvas_frame,
                bg="#2d2d2d",
                highlightthickness=0,
                height=150
            )
            scrollbar = ttk.Scrollbar(
                canvas_frame,
                orient="vertical",
                command=self.button_canvas.yview
            )

            self.button_container = tk.Frame(self.button_canvas, bg="#2d2d2d")

            self.button_container.bind(
                "<Configure>",
                lambda e: self.button_canvas.configure(scrollregion=self.button_canvas.bbox("all"))
            )

            self.button_canvas.create_window((0, 0), window=self.button_container, anchor="nw")
            self.button_canvas.configure(yscrollcommand=scrollbar.set)

            self.button_canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")

            def _on_mousewheel(event):
                self.button_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            self.button_canvas.bind("<Enter>", lambda e: self.button_canvas.bind_all("<MouseWheel>", _on_mousewheel))
            self.button_canvas.bind("<Leave>", lambda e: self.button_canvas.unbind_all("<MouseWheel>"))
            self.button_container.bind("<Enter>", lambda e: self.button_canvas.bind_all("<MouseWheel>", _on_mousewheel))
            self.button_container.bind("<Leave>", lambda e: self.button_canvas.unbind_all("<MouseWheel>"))

            # Status label for auto-creation
            self.status_label = tk.Label(
                button_frame,
                text="Connect device to automatically synchronize button bindings",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 9, "italic"),
                wraplength=850
            )
            #self.status_label.grid(row=2, column=0, sticky="ew", pady=5)

            self.frame = button_frame

        except Exception as e:
            log_error(e, "Error creating button section")

    def load_bindings(self, config):
        """Load bindings from config and create UI rows."""
        try:
            # Clear existing rows first
            for widget in self.button_container.winfo_children():
                widget.destroy()

            self.button_binding_rows = {}

            # If device is connected, use device-based synchronization
            if self.device_button_count > 0:
                self._synchronize_button_bindings(self.device_button_count)
            else:
                # Load bindings from config (no device connected)
                button_bindings = config.get('button_bindings', {})

                for button_name, binding in button_bindings.items():
                    if isinstance(binding, dict):
                        action = binding.get('action', '')
                        target = binding.get('target', '')
                        keybind = binding.get('keybind', '')
                        app_path = binding.get('app_path', '')
                        output_mode = binding.get('output_mode', 'cycle')
                        output_device = binding.get('output_device', '')
                    else:
                        action = binding
                        target = ''
                        keybind = ''
                        app_path = ''
                        output_mode = 'cycle'
                        output_device = ''

                    if button_name:
                        # Create display name
                        if button_name.startswith('b'):
                            button_num = button_name[1:]
                            display_name = f"Button {button_num}"
                        else:
                            display_name = button_name

                        self._add_button_binding_row(
                            button_name=button_name,
                            display_name=display_name,
                            action=action,
                            target=target,
                            keybind=keybind,
                            app_path=app_path,
                            output_mode=output_mode,
                            output_device=output_device,
                            is_auto=False
                        )

                # Update status label
                if self.status_label:
                    button_count = len([name for name in button_bindings.keys() if name.startswith('b')])
                    self.status_label.config(
                        text=f"Showing {button_count} button bindings from config (no device connected)")

        except Exception as e:
            log_error(e, "Error loading button bindings")

    def _get_audio_output_devices(self):
        """Get available audio output device names"""
        try:
            from utils.output_switch import get_device_names
            return get_device_names()
        except Exception as e:
            log_error(e, "Error getting audio devices")
            return []

    async def _get_audio_output_devices_async(self):
        """Get available audio output device names asynchronously"""
        try:
            from utils.output_switch import get_device_names
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            from concurrent.futures import ThreadPoolExecutor
            executor = ThreadPoolExecutor(max_workers=1)
            devices = await loop.run_in_executor(executor, get_device_names)
            return devices
        except Exception as e:
            log_error(e, "Error getting audio devices")
            return []

    def _refresh_audio_devices(self, output_mode_combo):
        """Refresh audio device list in dropdown (async, non-blocking)"""

        async def refresh():
            try:
                devices = await self._get_audio_output_devices_async()
                output_options = ["Cycle Through"] + devices

                # Update UI in main thread
                def update_ui():
                    try:
                        current = output_mode_combo.get()
                        output_mode_combo['values'] = output_options
                        # Keep current selection if still valid
                        if current not in output_options:
                            output_mode_combo.set("Cycle Through")
                    except Exception as e:
                        log_error(e, "Error updating device list UI")

                # Schedule UI update in main thread
                output_mode_combo.after(0, update_ui)
            except Exception as e:
                log_error(e, "Error refreshing audio devices")

        self._run_async(refresh())

    def _auto_save_button_binding(self, button_name, action_combo, target_combo,
                                  keybind_entry, app_path_entry, output_mode_combo, output_device_combo):
        """Automatically save button binding when changes occur."""
        try:
            action = self.helpers.normalize_action_name(action_combo.get().strip())

            if not button_name or not button_name.startswith('b'):
                return False

            target = None
            if action == "mute" and target_combo.winfo_ismapped():
                target = self.helpers.normalize_target_name(target_combo.get().strip())

            keybind = None
            if action == "keybind" and keybind_entry.winfo_ismapped():
                keybind = keybind_entry.get().strip()

            app_path = None
            if action == "launch_app" and app_path_entry.winfo_ismapped():
                app_path = app_path_entry.get().strip()

            output_mode = None
            output_device = None
            if action == "switch_audio_output":
                if output_mode_combo.winfo_ismapped():
                    output_selection = output_mode_combo.get().strip()
                    if output_selection and output_selection != "Cycle Through":
                        output_mode = "select"
                        output_device = output_selection
                    else:
                        output_mode = "cycle"
                        output_device = None

            binding_data = {
                'action': action,
                'target': target if target and target != "None" else None,
                'keybind': keybind if keybind else None,
                'app_path': app_path if app_path else None,
                'output_mode': output_mode if output_mode else None,
                'output_device': output_device if output_device else None
            }

            if self.config_manager.add_button_binding(button_name, binding_data):
                return True

            return False

        except Exception as e:
            log_error(e, "Error auto-saving button binding")
            return False

    def _add_button_binding_row(self, button_name="", display_name="", action="", target="",
                                keybind="", app_path="", output_mode="cycle", output_device="", is_auto=False):
        """Add a button binding row with responsive layout"""
        try:
            row_frame = tk.Frame(self.button_container, bg="#353535", padx=6, pady=4)
            row_frame.pack(fill="x", padx=3, pady=2)

            # Store row data
            self.button_binding_rows[button_name] = {
                'frame': row_frame,
                'is_auto': is_auto,
                'button_name': button_name
            }

            row_frame.grid_columnconfigure(1, weight=0)
            row_frame.grid_columnconfigure(3, weight=0)
            row_frame.grid_columnconfigure(5, weight=1)

            # Button name (display only, not editable)
            tk.Label(
                row_frame,
                text=f"{display_name}:",
                bg="#353535",
                fg="white",
                font=("Arial", 9, "bold")
            ).grid(row=0, column=0, padx=2, sticky="w")

            tk.Label(
                row_frame,
                text="→",
                bg="#353535",
                fg="#00ff00",
                font=("Arial", 10, "bold")
            ).grid(row=0, column=1, padx=2)

            # Action dropdown
            tk.Label(
                row_frame,
                text="Action:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            ).grid(row=0, column=2, padx=2, sticky="w")

            actions = self.helpers.get_available_actions()

            action_var = tk.StringVar()
            action_combo = ttk.Combobox(
                row_frame,
                textvariable=action_var,
                values=actions,
                state="readonly",
                width=18,
                font=("Arial", 9)
            )
            action_combo.grid(row=0, column=3, padx=2, sticky="w")

            if action:
                display_action = self.helpers.get_action_display_name(action)
                if display_action in actions:
                    action_combo.set(display_action)

            # Dynamic elements container
            dynamic_frame = tk.Frame(row_frame, bg="#353535")
            dynamic_frame.grid(row=0, column=4, padx=2, sticky="ew")

            # Target (for mute action)
            target_label = tk.Label(
                dynamic_frame,
                text="Target:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            )

            target_var = tk.StringVar()
            target_combo = ttk.Combobox(
                dynamic_frame,
                textvariable=target_var,
                values=self.helpers.get_available_targets(),
                width=15,
                font=("Arial", 9)
            )

            if target:
                display_target = self.helpers.get_display_name(target)
                target_combo.set(display_target)

            # Keybind entry (shown when action is keybind)
            keybind_label = tk.Label(
                dynamic_frame,
                text="Keys:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            )

            keybind_entry = tk.Entry(dynamic_frame, width=15, font=("Arial", 9))
            if keybind and isinstance(keybind, str):
                keybind_entry.insert(0, keybind)

            # App path entry (shown when action is launch_app)
            app_path_label = tk.Label(
                dynamic_frame,
                text="Path:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            )

            app_path_entry = tk.Entry(dynamic_frame, width=25, font=("Arial", 9))
            if app_path and isinstance(app_path, str):
                app_path_entry.insert(0, app_path)

            # Audio output selector (shown when action is switch_audio_output)
            output_label = tk.Label(
                dynamic_frame,
                text="Device:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            )

            output_var = tk.StringVar()

            # Get available audio devices
            audio_devices = self._get_audio_output_devices()
            output_options = ["Cycle Through"] + audio_devices

            output_mode_combo = ttk.Combobox(
                dynamic_frame,
                textvariable=output_var,
                values=output_options,
                width=20,
                font=("Arial", 9)
            )

            # Set initial value for audio output
            if output_mode == "cycle" or not output_device:
                output_mode_combo.set("Cycle Through")
            elif output_mode == "select" and output_device:
                # Check if the device still exists in the list
                if output_device in audio_devices:
                    output_mode_combo.set(output_device)
                else:
                    output_mode_combo.set("Cycle Through")
            else:
                output_mode_combo.set("Cycle Through")

            # Add refresh button for audio devices
            refresh_btn = tk.Button(
                dynamic_frame,
                text="🔄",
                command=lambda: self._refresh_audio_devices(output_mode_combo),
                bg="#404040",
                fg="white",
                font=("Arial", 8),
                relief="flat",
                padx=3,
                pady=1,
                cursor="hand2"
            )

            # BIND AUTO-SAVE TO ALL ENTRIES
            def auto_save_wrapper(e=None):
                return self._auto_save_button_binding(
                    button_name, action_combo, target_combo,
                    keybind_entry, app_path_entry, output_mode_combo, output_mode_combo
                )

            target_combo.bind('<<ComboboxSelected>>', auto_save_wrapper)
            keybind_entry.bind('<FocusOut>', auto_save_wrapper)
            app_path_entry.bind('<FocusOut>', auto_save_wrapper)
            output_mode_combo.bind('<<ComboboxSelected>>', auto_save_wrapper)

            # Show/hide elements based on action
            def on_action_change(event=None):
                for widget in dynamic_frame.winfo_children():
                    widget.pack_forget()

                action_name = self.helpers.normalize_action_name(action_var.get())

                if action_name == "keybind":
                    keybind_label.pack(side="left", padx=2)
                    keybind_entry.pack(side="left", padx=2)
                elif action_name == "mute":
                    target_label.pack(side="left", padx=2)
                    target_combo.pack(side="left", padx=2)
                elif action_name == "launch_app":
                    app_path_label.pack(side="left", padx=2)
                    app_path_entry.pack(side="left", padx=2)
                elif action_name == "switch_audio_output":
                    output_label.pack(side="left", padx=2)
                    output_mode_combo.pack(side="left", padx=2)
                    refresh_btn.pack(side="left", padx=2)

            # BIND AUTO-SAVE TO ACTION COMBO AND CALL on_action_change
            action_combo.bind('<<ComboboxSelected>>',
                              lambda e: (on_action_change(e), auto_save_wrapper(e))
                              )

            on_action_change()  # Initial state

            # Button container
            btn_frame = tk.Frame(row_frame, bg="#353535")
            btn_frame.grid(row=0, column=5, padx=2, sticky="e")

            # Test button
            test_btn = tk.Button(
                btn_frame,
                text="▶️",
                command=lambda: self._test_button_action(
                    self.helpers.normalize_action_name(action_var.get()),
                    self.helpers.normalize_target_name(target_var.get()) if target_var.get() else "",
                    keybind_entry.get(),
                    app_path_entry.get(),
                    output_var.get()
                ),
                bg="#404040",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=5,
                pady=2,
                cursor="hand2"
            )
            test_btn.pack(side="left", padx=1)

            # Clear binding button (instead of delete)
            clear_btn = tk.Button(
                btn_frame,
                text="🗑",
                command=lambda: self._clear_button_binding(button_name, row_frame, action_combo, dynamic_frame),
                bg="#5c1a1a",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=5,
                pady=2,
                cursor="hand2"
            )
            clear_btn.pack(side="left", padx=1)

        except Exception as e:
            log_error(e, "Error adding button binding row")

    def _test_button_action(self, action, target, keybind, app_path, output_selection):
        """Test a button action (handles async actions properly)"""
        try:
            from utils.actions import ActionHandler

            action_handler = ActionHandler(self.audio_manager)

            kwargs = {}
            if action == "mute" and target:
                kwargs['target'] = target
            elif action == "keybind" and keybind:
                kwargs['keys'] = keybind
            elif action == "launch_app" and app_path:
                kwargs['app_path'] = app_path
            elif action == "switch_audio_output":
                if output_selection == "Cycle Through":
                    kwargs['output_mode'] = 'cycle'
                else:
                    kwargs['output_mode'] = 'select'
                    kwargs['device_name'] = output_selection

            success = action_handler.execute_action(action, **kwargs)

            # Show feedback immediately for async actions
            if action == "switch_audio_output":
                messagebox.showinfo("Test", f"Audio output switch initiated!\nSwitching in background...")
            elif success:
                messagebox.showinfo("Test", f"Action '{action}' executed successfully!")
            else:
                messagebox.showwarning("Test", f"Action '{action}' failed to execute")

        except Exception as e:
            messagebox.showerror("Error", f"Error testing button action: {str(e)}")
            log_error(e, "Error testing button action")

    def _clear_button_binding(self, button_name, frame, action_combo, dynamic_frame):
        """Clear a button binding (set to empty action) instead of deleting"""
        try:
            if button_name:
                # Clear the binding in config
                self.config_manager.add_button_binding(button_name, {})

                # Clear the UI
                action_combo.set('')

                # Clear dynamic frame
                for widget in dynamic_frame.winfo_children():
                    widget.pack_forget()

        except Exception as e:
            log_error(e, "Error clearing button binding")