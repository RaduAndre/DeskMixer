# ui/config_bindings_section.py
import tkinter as tk
from tkinter import ttk, messagebox
from utils.error_handler import log_error


class ConfigBindingsSection:
    """Handles the Variable Bindings UI and logic."""

    def __init__(self, parent_frame, audio_manager, config_manager, common_helpers, serial_handler=None):
        self.audio_manager = audio_manager
        self.config_manager = config_manager
        self.helpers = common_helpers
        self.serial_handler = serial_handler

        self.bindings_canvas = None
        self.bindings_container = None
        self.slider_sampling_combo = None
        self.tooltip_id = None
        self.binding_rows = {}  # Store rows by variable name
        self.device_slider_count = 0  # Track device configuration

        self._create_ui(parent_frame)

        # Register for configuration updates if serial_handler is provided
        if self.serial_handler:
            self.serial_handler.add_config_callback(self._on_device_config)

        # Load existing bindings and global mode after UI is created
        self._load_slider_sampling()
        self._load_existing_bindings()

    def _on_device_config(self, slider_count, button_count):
        """Handle device configuration updates - automatically create/remove binding rows"""
        try:
            self.device_slider_count = slider_count
            print(f"Device config: {slider_count} sliders, creating/updating binding rows")
            self._synchronize_slider_bindings(slider_count)
        except Exception as e:
            log_error(e, "Error creating slider bindings from device config")

    def _synchronize_slider_bindings(self, device_slider_count):
        """Synchronize UI with device configuration - create missing or remove extra rows"""
        try:
            # Get current config bindings
            config = self.config_manager.load_config()
            config_bindings = config.get('variable_bindings', {})

            # Find which sliders exist in config
            config_sliders = set()
            for var_name in config_bindings.keys():
                if var_name.startswith('s') and var_name[1:].isdigit():
                    config_sliders.add(int(var_name[1:]))

            print(f"Config has sliders: {sorted(config_sliders)}")
            print(f"Device has sliders: {list(range(1, device_slider_count + 1))}")

            # Create set of required sliders (union of config and device)
            required_sliders = set(range(1, device_slider_count + 1)).union(config_sliders)
            print(f"Required sliders: {sorted(required_sliders)}")

            # Remove UI rows for sliders that are not in required_sliders
            rows_to_remove = []
            for var_name, row_data in self.binding_rows.items():
                if var_name.startswith('s'):
                    slider_num = int(var_name[1:])
                    if slider_num not in required_sliders:
                        rows_to_remove.append(var_name)

            for var_name in rows_to_remove:
                row_data = self.binding_rows[var_name]
                row_data['frame'].destroy()
                del self.binding_rows[var_name]
                print(f"Removed UI row for {var_name} (not in device or config)")

            # Create UI rows for missing sliders
            for slider_num in sorted(required_sliders):
                var_name = f"s{slider_num}"
                display_name = f"Slider {slider_num}"

                # Skip if row already exists
                if var_name in self.binding_rows:
                    continue

                # Check if binding exists in config
                existing_binding = self.config_manager.load_variable_binding(var_name)
                app_names = existing_binding if existing_binding else ["None"]

                # Determine if this is auto-created (not in config but in device)
                is_auto = (slider_num <= device_slider_count and slider_num not in config_sliders)

                # Create the row
                self._add_binding_row(var_name, display_name, app_names, is_auto=is_auto)

                if is_auto:
                    print(f"Auto-created UI row for {var_name}")
                else:
                    print(f"Created UI row for {var_name} from config")

            # Update status label
            if self.status_label:
                visible_count = len([name for name in self.binding_rows.keys() if name.startswith('s')])
                self.status_label.config(
                    text=f"Showing {visible_count} slider bindings ({device_slider_count} from device)")

        except Exception as e:
            log_error(e, "Error synchronizing slider bindings")

    def _create_ui(self, parent):
        """Create variable bindings section"""
        try:
            bindings_frame = tk.LabelFrame(
                parent,
                text="Slider bindings - Volume Control",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=10
            )
            bindings_frame.grid_rowconfigure(2, weight=1)
            bindings_frame.grid_columnconfigure(0, weight=1)

            # Help text
            help_text = tk.Label(
                bindings_frame,
                text="Bind the volume source you prefer on each slider.",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 8),
                wraplength=850,
                justify="left"
            )
            help_text.grid(row=0, column=0, sticky="ew", pady=(0, 5))

            # Slider Sampling Mode Control (Subtle)
            mode_control_frame = tk.Frame(bindings_frame, bg="#2d2d2d")
            mode_control_frame.grid(row=1, column=0, sticky="w", pady=(0, 8), padx=2)

            tk.Label(
                mode_control_frame,
                text="Slider Sampling:",
                bg="#2d2d2d",
                fg="#aaaaaa",
                font=("Arial", 9)
            ).pack(side="left", padx=(0, 8))

            self.slider_sampling_combo = ttk.Combobox(
                mode_control_frame,
                values=["soft", "normal", "hard"],
                state="readonly",
                width=10,
                font=("Arial", 9)
            )
            self.slider_sampling_combo.pack(side="left")

            # Bind change event
            self.slider_sampling_combo.bind('<<ComboboxSelected>>', self._on_slider_sampling_change)

            # Bind hover events for tooltip
            self.slider_sampling_combo.bind('<Enter>', self._schedule_tooltip)
            self.slider_sampling_combo.bind('<Leave>', self._hide_tooltip)
            self.slider_sampling_combo.bind('<Motion>', self._schedule_tooltip)

            # Scrollable container with responsive canvas
            canvas_frame = tk.Frame(bindings_frame, bg="#2d2d2d")
            canvas_frame.grid(row=2, column=0, sticky="nsew")
            canvas_frame.grid_rowconfigure(0, weight=1)
            canvas_frame.grid_columnconfigure(0, weight=1)

            self.bindings_canvas = tk.Canvas(
                canvas_frame,
                bg="#2d2d2d",
                highlightthickness=0,
                height=150
            )
            scrollbar = ttk.Scrollbar(
                canvas_frame,
                orient="vertical",
                command=self.bindings_canvas.yview
            )

            self.bindings_container = tk.Frame(self.bindings_canvas, bg="#2d2d2d")

            self.bindings_container.bind(
                "<Configure>",
                lambda e: self.bindings_canvas.configure(scrollregion=self.bindings_canvas.bbox("all"))
            )

            self.bindings_canvas.create_window((0, 0), window=self.bindings_container, anchor="nw")
            self.bindings_canvas.configure(yscrollcommand=scrollbar.set)

            self.bindings_canvas.grid(row=0, column=0, sticky="nsew")
            scrollbar.grid(row=0, column=1, sticky="ns")

            # Bind mouse wheel only to canvas and its children
            self._bind_mousewheel(self.bindings_canvas)
            self._bind_mousewheel(self.bindings_container)

            # Status label for auto-creation
            self.status_label = tk.Label(
                bindings_frame,
                text="Connect device to automatically synchronize slider bindings",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 9, "italic"),
                wraplength=850
            )
            #self.status_label.grid(row=3, column=0, sticky="ew", pady=5)

            self.frame = bindings_frame

        except Exception as e:
            log_error(e, "Error creating bindings section")

    def _bind_mousewheel(self, widget):
        """Bind mousewheel to a specific widget"""
        widget.bind('<Enter>', lambda e: widget.bind_all('<MouseWheel>', self._on_canvas_mousewheel))
        widget.bind('<Leave>', lambda e: widget.unbind_all('<MouseWheel>'))

    def _on_canvas_mousewheel(self, event):
        """Handle mousewheel scrolling for canvas only"""
        self.bindings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _schedule_tooltip(self, event):
        """Schedule tooltip to appear after delay"""
        self._hide_tooltip()
        self.tooltip_id = self.slider_sampling_combo.after(800, lambda: self._show_tooltip(event))

    def _show_tooltip(self, event):
        """Show tooltip with mode descriptions"""
        try:
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

            label = tk.Label(
                tooltip,
                text="Soft: Gentle curve (more responsive at low volumes)\n"
                     "Normal: Linear 1:1 response\n"
                     "Hard: Sharp curve (more precise at high volumes)\n\n"
                     "Applies to all variable bindings",
                justify="left",
                background="#ffffcc",
                foreground="#000000",
                relief="solid",
                borderwidth=1,
                font=("Arial", 8),
                padx=8,
                pady=6
            )
            label.pack()

            self.tooltip_window = tooltip

        except Exception as e:
            log_error(e, "Error showing tooltip")

    def _hide_tooltip(self, event=None):
        """Hide tooltip"""
        if self.tooltip_id:
            self.slider_sampling_combo.after_cancel(self.tooltip_id)
            self.tooltip_id = None

        if hasattr(self, 'tooltip_window'):
            try:
                self.tooltip_window.destroy()
            except:
                pass
            delattr(self, 'tooltip_window')

    def _load_slider_sampling(self):
        """Load and set the global mode from config"""
        try:
            current_mode = self.config_manager.get_slider_sampling('normal')
            if self.slider_sampling_combo:
                self.slider_sampling_combo.set(current_mode)
        except Exception as e:
            log_error(e, "Error loading global mode")
            if self.slider_sampling_combo:
                self.slider_sampling_combo.set('normal')

    def _on_slider_sampling_change(self, event=None):
        """Handle global mode change"""
        try:
            new_mode = self.slider_sampling_combo.get()
            self.config_manager.set_slider_sampling(new_mode)
        except Exception as e:
            log_error(e, "Error changing global mode")

    def _load_existing_bindings(self):
        """Load existing bindings from config on initialization"""
        try:
            config = self.config_manager.load_config()
            variable_bindings = config.get('variable_bindings', {})

            if variable_bindings:
                # Sort by variable name for consistent display
                sorted_bindings = sorted(variable_bindings.items(), key=lambda x: x[0])

                for var_name, binding_data in sorted_bindings:
                    # Handle multiple formats: string, list, or dict
                    if isinstance(binding_data, dict):
                        app_names = binding_data.get('app_name', [])
                        if isinstance(app_names, str):
                            app_names = [app_names]
                    elif isinstance(binding_data, list):
                        app_names = binding_data
                    else:
                        app_names = [binding_data] if binding_data else []

                    # Create display name
                    if var_name.startswith('s'):
                        slider_num = var_name[1:]
                        display_name = f"Slider {slider_num}"
                    else:
                        display_name = var_name

                    self._add_binding_row(var_name, display_name, app_names, is_auto=False)

        except Exception as e:
            log_error(e, "Error loading existing bindings")

    def _add_binding_row(self, var_name, display_name, app_names=None, is_auto=False):
        """Add a variable binding row with multiple target selectors"""
        try:
            if app_names is None:
                app_names = []
            elif isinstance(app_names, str):
                app_names = [app_names] if app_names else []

            # Ensure at least one target
            if not app_names:
                app_names = ["None"]

            row_frame = tk.Frame(self.bindings_container, bg="#353535", padx=6, pady=4)
            row_frame.pack(fill="x", padx=3, pady=2)

            # Store row data
            self.binding_rows[var_name] = {
                'frame': row_frame,
                'is_auto': is_auto,
                'var_name': var_name
            }

            # Bind mousewheel to row frame
            self._bind_mousewheel(row_frame)

            # Use grid for better control
            row_frame.grid_columnconfigure(3, weight=1)

            # Variable name (display only, not editable)
            tk.Label(
                row_frame,
                text=f"{display_name}:",
                bg="#353535",
                fg="white",
                font=("Arial", 9, "bold")
            ).grid(row=0, column=0, padx=(5, 2), sticky="nw", pady=5)

            tk.Label(
                row_frame,
                text="→",
                bg="#353535",
                fg="#00ff00",
                font=("Arial", 10, "bold")
            ).grid(row=0, column=1, padx=5, sticky="nw", pady=5)

            # Create frame for targets (will contain multiple selectors)
            targets_frame = tk.Frame(row_frame, bg="#353535")
            targets_frame.grid(row=0, column=2, sticky="ew", padx=2)

            # Store reference to targets container
            row_frame.targets_frame = targets_frame
            row_frame.var_name = var_name
            row_frame.target_selectors = []

            # Create initial target selectors
            for app_name in app_names:
                self._add_target_selector(row_frame, app_name)

            # Clear binding button (instead of delete)
            clear_btn = tk.Button(
                row_frame,
                text="🗑",
                command=lambda: self._clear_binding(var_name, row_frame),
                bg="#5c1a1a",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2"
            )
            clear_btn.grid(row=0, column=3, padx=(10, 5), sticky="ne", pady=5)

            # Hover effects
            clear_btn.bind('<Enter>', lambda e: clear_btn.config(bg="#7d2424"))
            clear_btn.bind('<Leave>', lambda e: clear_btn.config(bg="#5c1a1a"))

        except Exception as e:
            log_error(e, "Error adding binding row")

    def _add_target_selector(self, row_frame, selected_app="None"):
        """Add a single target selector with + and - buttons"""
        try:
            targets_frame = row_frame.targets_frame

            # Create container for this selector
            selector_frame = tk.Frame(targets_frame, bg="#353535")
            selector_frame.pack(fill="x", pady=2)

            # Get available targets
            targets = self.helpers.get_available_targets()

            # Add "Select another app..." option at the end
            targets.append("─────────────────────")
            targets.append("🔍 Select another app...")

            # Combobox (editable to allow custom app names)
            combo = ttk.Combobox(
                selector_frame,
                values=targets,
                width=30,
                font=("Arial", 9)
            )
            combo.pack(side="left", padx=2)

            # Set current value
            display_name = self.helpers.get_display_name(selected_app)
            if display_name and display_name not in targets:
                # Add custom app to list
                separator_idx = -1
                for idx, target in enumerate(targets):
                    if target.startswith("─"):
                        separator_idx = idx
                        break

                if separator_idx > 0:
                    targets.insert(separator_idx + 1, display_name)
                else:
                    # Insert before the last separator and browse option
                    targets.insert(-2, display_name)
                combo['values'] = targets

            combo.set(display_name if display_name else "❌ None")

            # Function to handle file browsing
            def on_browse_file():
                """Open file dialog to select an executable"""
                try:
                    from tkinter import filedialog
                    import os

                    # Open file dialog
                    file_path = filedialog.askopenfilename(
                        title="Select Application",
                        filetypes=[
                            ("Executable files", "*.exe"),
                            ("All files", "*.*")
                        ],
                        initialdir=os.path.expandvars(r"%ProgramFiles%")
                    )

                    if file_path:
                        # Extract just the executable name (e.g., "chrome.exe")
                        exe_name = os.path.basename(file_path)

                        # Update the combobox with the exe name
                        current_targets = list(combo['values'])

                        # Find the separator before "Select another app..."
                        separator_idx = -1
                        for idx, target in enumerate(current_targets):
                            if target.startswith("─") and idx < len(current_targets) - 1:
                                if "Select another app" in current_targets[idx + 1]:
                                    separator_idx = idx
                                    break

                        # Add the new app if not already in list
                        if exe_name not in current_targets:
                            if separator_idx > 0:
                                current_targets.insert(separator_idx + 1, exe_name)
                            else:
                                current_targets.insert(-2, exe_name)
                            combo['values'] = current_targets

                        # Set the selected value
                        combo.set(exe_name)

                        # Clear selection and remove focus to prevent text highlighting
                        combo.selection_clear()
                        combo.icursor(tk.END)  # Move cursor to end

                        # Remove focus from combobox
                        self.bindings_container.focus_set()

                        # Trigger auto-save
                        self._auto_save_binding(row_frame)

                except Exception as e:
                    log_error(e, "Error browsing for file")
                    messagebox.showerror("Error", f"Failed to select file: {str(e)}")

            # Function to handle selection change
            def on_combo_select(event):
                """Handle combobox selection"""
                selected = combo.get()
                if selected == "🔍 Select another app...":
                    # Reset to previous value temporarily
                    combo.set(display_name if display_name else "❌ None")
                    # Open file browser
                    on_browse_file()
                else:
                    # Normal selection - trigger auto-save
                    self._auto_save_binding(row_frame)

            # Auto-refresh function when dropdown is opened
            def on_dropdown_open(event):
                """Refresh the app list when dropdown is clicked"""
                try:
                    current_value = combo.get()

                    # Don't refresh if "Select another app..." is selected
                    if current_value == "🔍 Select another app...":
                        return

                    updated_targets = self.helpers.get_available_targets()

                    # Add separators and browse option
                    updated_targets.append("─────────────────────")
                    updated_targets.append("🔍 Select another app...")

                    # Add current value to targets if not present
                    if current_value and current_value not in updated_targets:
                        # Find separator before browse option
                        separator_idx = -1
                        for idx, target in enumerate(updated_targets):
                            if target.startswith("─") and idx < len(updated_targets) - 1:
                                if "Select another app" in updated_targets[idx + 1]:
                                    separator_idx = idx
                                    break

                        if separator_idx > 0:
                            updated_targets.insert(separator_idx + 1, current_value)
                        else:
                            updated_targets.insert(-2, current_value)

                    combo['values'] = updated_targets
                    # Keep the current selection
                    combo.set(current_value)
                except Exception as e:
                    log_error(e, "Error refreshing dropdown")

            # Bind the dropdown open event
            combo.bind('<Button-1>', on_dropdown_open)
            combo.bind('<Down>', on_dropdown_open)  # Also refresh on keyboard navigation

            # Plus button to add another selector
            plus_btn = tk.Button(
                selector_frame,
                text="➕",
                command=lambda: self._add_target_selector(row_frame, "None"),
                bg="#2d5c2d",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=6,
                pady=2,
                cursor="hand2"
            )
            plus_btn.pack(side="left", padx=2)

            # Minus button to remove this selector
            minus_btn = tk.Button(
                selector_frame,
                text="➖",
                command=lambda: self._remove_target_selector(row_frame, selector_frame),
                bg="#5c2d2d",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=6,
                pady=2,
                cursor="hand2"
            )
            minus_btn.pack(side="left", padx=2)

            # Store reference
            selector_data = {
                'frame': selector_frame,
                'combo': combo,
                'plus_btn': plus_btn,
                'minus_btn': minus_btn
            }
            row_frame.target_selectors.append(selector_data)

            # Update minus button visibility
            self._update_minus_button_visibility(row_frame)

            # Bind events for auto-save
            combo.bind('<<ComboboxSelected>>', on_combo_select)
            combo.bind('<FocusOut>',
                       lambda e: self._auto_save_binding(row_frame))
            combo.bind('<Return>',
                       lambda e: self._auto_save_binding(row_frame))

        except Exception as e:
            log_error(e, "Error adding target selector")

    def _update_minus_button_visibility(self, row_frame):
        """Show/hide minus buttons based on number of selectors"""
        try:
            num_selectors = len(row_frame.target_selectors)

            for selector_data in row_frame.target_selectors:
                if num_selectors <= 1:
                    # Hide minus button if only one selector
                    selector_data['minus_btn'].pack_forget()
                else:
                    # Show minus button if multiple selectors
                    selector_data['minus_btn'].pack(side="left", padx=2)

        except Exception as e:
            log_error(e, "Error updating minus button visibility")

    def _remove_target_selector(self, row_frame, selector_frame):
        """Remove a target selector"""
        try:
            # Don't allow removing if only one selector remains
            if len(row_frame.target_selectors) <= 1:
                return

            # Find and remove from list
            for i, selector_data in enumerate(row_frame.target_selectors):
                if selector_data['frame'] == selector_frame:
                    row_frame.target_selectors.pop(i)
                    break

            # Destroy the frame
            selector_frame.destroy()

            # Update minus button visibility
            self._update_minus_button_visibility(row_frame)

            # Save changes
            self._auto_save_binding(row_frame)

        except Exception as e:
            log_error(e, "Error removing target selector")

    def load_bindings(self, config=None):
        """Load bindings from config and create UI rows (external call support)"""
        try:
            if config is None:
                config = self.config_manager.load_config()

            # Clear existing rows first
            for widget in self.bindings_container.winfo_children():
                widget.destroy()

            self.binding_rows = {}

            # Reload global mode
            self._load_slider_sampling()

            # If device is connected, use device-based synchronization
            if self.device_slider_count > 0:
                self._synchronize_slider_bindings(self.device_slider_count)
            else:
                # Load bindings from config (no device connected)
                variable_bindings = config.get('variable_bindings', {})
                sorted_bindings = sorted(variable_bindings.items(), key=lambda x: x[0])

                for var_name, binding_data in sorted_bindings:
                    # Handle multiple formats
                    if isinstance(binding_data, dict):
                        app_names = binding_data.get('app_name', [])
                        if isinstance(app_names, str):
                            app_names = [app_names]
                    elif isinstance(binding_data, list):
                        app_names = binding_data
                    else:
                        app_names = [binding_data] if binding_data else []

                    # Create display name
                    if var_name.startswith('s'):
                        slider_num = var_name[1:]
                        display_name = f"Slider {slider_num}"
                    else:
                        display_name = var_name

                    self._add_binding_row(var_name, display_name, app_names, is_auto=False)

                # Update status label
                if self.status_label:
                    slider_count = len([name for name in variable_bindings.keys() if name.startswith('s')])
                    self.status_label.config(
                        text=f"Showing {slider_count} slider bindings from config (no device connected)")

        except Exception as e:
            log_error(e, "Error loading bindings")

    def _auto_save_binding(self, row_frame):
        """Automatically save binding when changes occur"""
        try:
            var_name = row_frame.var_name

            # Get selected apps from all selectors
            selected_apps = []

            for selector_data in row_frame.target_selectors:
                combo = selector_data['combo']
                display_name = combo.get().strip()
                normalized = self.helpers.normalize_target_name(display_name)

                # If it's not a recognized target, treat as custom app name
                if not normalized and display_name and not display_name.startswith("─"):
                    normalized = display_name

                if normalized:
                    selected_apps.append(normalized)

            if var_name and var_name.startswith(('s', 'p')):
                # Check for duplicates and handle them (returns True if we should save)
                if self._check_and_handle_duplicates(var_name, selected_apps, row_frame):
                    # Save the binding for current variable
                    self.config_manager.add_binding(var_name, selected_apps)
                    return True

        except Exception as e:
            log_error(e, "Error auto-saving binding")
            return False

    def _check_and_handle_duplicates(self, current_var, selected_apps, current_row_frame):
        """Check for duplicate bindings and replace old ones with None"""
        try:
            config = self.config_manager.load_config()
            bindings = config.get('variable_bindings', {})

            modified = False

            # Check all selected apps
            for app in selected_apps:
                if app == "None":
                    continue  # Skip None

                # Check if this app is bound elsewhere
                for var, binding_data in list(bindings.items()):
                    if var == current_var:
                        continue

                    # Get apps for this variable
                    if isinstance(binding_data, dict):
                        apps = binding_data.get('app_name', [])
                    elif isinstance(binding_data, list):
                        apps = binding_data
                    else:
                        apps = [binding_data] if binding_data else []

                    if isinstance(apps, str):
                        apps = [apps]

                    # If this app is found in another binding
                    if app in apps:
                        # Replace it with None
                        new_apps = ["None" if old_app == app else old_app for old_app in apps]
                        bindings[var] = new_apps
                        modified = True

            if modified:
                # Save other bindings first
                self.config_manager.config['variable_bindings'] = bindings

                # Now save the current binding
                bindings[current_var] = selected_apps
                self.config_manager.config['variable_bindings'] = bindings
                self.config_manager.save_config()

                # Reload UI to reflect all changes
                self.load_bindings()
                return False  # Return False because we already saved and reloaded

            return True  # Return True to allow normal save

        except Exception as e:
            log_error(e, "Error checking duplicates")
            return True

    def _clear_binding(self, var_name, frame):
        """Clear a variable binding (set to None) instead of deleting"""
        try:
            if not var_name:
                return

            # Set binding to None
            self.config_manager.add_binding(var_name, ["None"])

            # Update UI - clear all target selectors and add one with "None"
            for selector_data in frame.target_selectors:
                selector_data['frame'].destroy()
            frame.target_selectors = []
            self._add_target_selector(frame, "None")

            # Auto-save the change
            self._auto_save_binding(frame)

        except Exception as e:
            log_error(e, f"Error clearing binding: {var_name}")