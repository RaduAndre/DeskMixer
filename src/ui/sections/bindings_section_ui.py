"""Bindings Section UI - Complete implementation for slider bindings

This is a full refactored implementation of the bindings section UI,
extracted from config_bindings_section.py (808 lines).
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from utils.error_handler import log_error
from ui.components import StyledLabelFrame, StyledFrame, StyledCombobox


class BindingsSectionUI:
    """Slider bindings section UI with handler-based logic"""

    def __init__(self, parent, handler):
        """
        Initialize bindings section UI

        Args:
            parent: Parent widget
            handler: BindingsSectionHandler instance
        """
        self.handler = handler
        self.frame = None
        self.binding_rows = {}

        # UI components
        self.bindings_canvas = None
        self.bindings_container = None
        self.slider_sampling_combo = None
        self.status_label = None
        self.tooltip_id = None

        self._create_ui(parent)
        self._register_callbacks()
        self._load_existing_bindings()
        self._load_slider_sampling()

    def _create_ui(self, parent):
        """Create variable bindings section"""
        try:
            bindings_frame = StyledLabelFrame(
                parent,
                text="Slider bindings - Volume Control"
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

            # Slider Sampling Mode Control
            self._create_mode_control(bindings_frame)

            # Scrollable container
            self._create_scrollable_container(bindings_frame)

            # Status label
            self.status_label = tk.Label(
                bindings_frame,
                text="Connect device to automatically synchronize slider bindings",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 9, "italic"),
                wraplength=850
            )

            self.frame = bindings_frame

        except Exception as e:
            log_error(e, "Error creating bindings section")

    def _create_mode_control(self, parent):
        """Create slider sampling mode control"""
        mode_control_frame = StyledFrame(parent)
        mode_control_frame.grid(row=1, column=0, sticky="w", pady=(0, 8), padx=2)

        tk.Label(
            mode_control_frame,
            text="Slider Sampling:",
            bg="#2d2d2d",
            fg="#aaaaaa",
            font=("Arial", 9)
        ).pack(side="left", padx=(0, 8))

        self.slider_sampling_combo = StyledCombobox(
            mode_control_frame,
            values=["soft", "normal", "hard"],
            width=10
        )
        self.slider_sampling_combo.pack(side="left")

        # Bind events
        self.slider_sampling_combo.bind('<<ComboboxSelected>>', self._on_slider_sampling_change)
        self.slider_sampling_combo.bind('<Enter>', self._schedule_tooltip)
        self.slider_sampling_combo.bind('<Leave>', self._hide_tooltip)
        self.slider_sampling_combo.bind('<Motion>', self._schedule_tooltip)

    def _create_scrollable_container(self, parent):
        """Create scrollable container for binding rows"""
        canvas_frame = StyledFrame(parent)
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

        self.bindings_container = StyledFrame(self.bindings_canvas)

        self.bindings_container.bind(
            "<Configure>",
            lambda e: self.bindings_canvas.configure(
                scrollregion=self.bindings_canvas.bbox("all")
            )
        )

        self.bindings_canvas.create_window(
            (0, 0),
            window=self.bindings_container,
            anchor="nw"
        )
        self.bindings_canvas.configure(yscrollcommand=scrollbar.set)

        self.bindings_canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # Mouse wheel scrolling
        self._bind_mousewheel(self.bindings_canvas)
        self._bind_mousewheel(self.bindings_container)

    def _bind_mousewheel(self, widget):
        """Bind mousewheel to a specific widget"""
        widget.bind('<Enter>', lambda e: widget.bind_all('<MouseWheel>', self._on_canvas_mousewheel))
        widget.bind('<Leave>', lambda e: widget.unbind_all('<MouseWheel>'))

    def _on_canvas_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        self.bindings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _schedule_tooltip(self, event):
        """Schedule tooltip to appear after delay"""
        self._hide_tooltip()
        self.tooltip_id = self.slider_sampling_combo.after(
            800,
            lambda: self._show_tooltip(event)
        )

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

    def _register_callbacks(self):
        """Register callbacks with handler"""
        self.handler.set_ui_callback(self._on_handler_event)
        self.handler.register_device_config_callback()

    def _on_handler_event(self, event_type, *args):
        """Handle events from the handler"""
        if event_type == 'device_config':
            slider_count, button_count = args
            self._synchronize_slider_bindings(slider_count)

    def _load_slider_sampling(self):
        """Load and set the global mode from config"""
        try:
            current_mode = self.handler.get_slider_sampling()
            if self.slider_sampling_combo:
                self.slider_sampling_combo.set(current_mode)
        except Exception as e:
            log_error(e, "Error loading slider sampling mode")
            if self.slider_sampling_combo:
                self.slider_sampling_combo.set('normal')

    def _on_slider_sampling_change(self, event=None):
        """Handle global mode change"""
        try:
            new_mode = self.slider_sampling_combo.get()
            self.handler.set_slider_sampling(new_mode)
        except Exception as e:
            log_error(e, "Error changing slider sampling mode")

    def _load_existing_bindings(self):
        """Load existing bindings from config on initialization"""
        try:
            variable_bindings = self.handler.load_variable_bindings()

            if variable_bindings:
                # Sort by variable name for consistent display
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

        except Exception as e:
            log_error(e, "Error loading existing bindings")

    def _synchronize_slider_bindings(self, device_slider_count):
        """Synchronize UI with device configuration"""
        try:
            required_sliders, config_sliders, device_sliders = self.handler.get_required_sliders()

            # Remove UI rows for sliders not in required set
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

            # Create UI rows for missing sliders
            for slider_num in sorted(required_sliders):
                var_name = f"s{slider_num}"
                display_name = f"Slider {slider_num}"

                if var_name in self.binding_rows:
                    continue

                # Check if binding exists in config
                existing_binding = self.handler.load_variable_binding(var_name)
                app_names = existing_binding if existing_binding else ["None"]

                # Determine if auto-created
                is_auto = (slider_num <= device_slider_count and
                          slider_num not in config_sliders)

                self._add_binding_row(var_name, display_name, app_names, is_auto=is_auto)

            # Update status label
            if self.status_label:
                visible_count = len([name for name in self.binding_rows.keys() if name.startswith('s')])
                self.status_label.config(
                    text=f"Showing {visible_count} slider bindings ({device_slider_count} from device)"
                )

        except Exception as e:
            log_error(e, "Error synchronizing slider bindings")

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

            # Bind mousewheel
            self._bind_mousewheel(row_frame)

            # Use grid for better control
            row_frame.grid_columnconfigure(3, weight=1)

            # Variable name label
            tk.Label(
                row_frame,
                text=f"{display_name}:",
                bg="#353535",
                fg="white",
                font=("Arial", 9, "bold")
            ).grid(row=0, column=0, padx=(5, 2), sticky="nw", pady=5)

            # Arrow
            tk.Label(
                row_frame,
                text="→",
                bg="#353535",
                fg="#00ff00",
                font=("Arial", 10, "bold")
            ).grid(row=0, column=1, padx=5, sticky="nw", pady=5)

            # Create frame for targets (multiple selectors)
            targets_frame = StyledFrame(row_frame, bg="#353535")
            targets_frame.grid(row=0, column=2, sticky="ew", padx=2)

            # Store reference
            row_frame.targets_frame = targets_frame
            row_frame.var_name = var_name
            row_frame.target_selectors = []

            # Create initial target selectors
            for app_name in app_names:
                self._add_target_selector(row_frame, app_name)

            # Clear binding button
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
            selector_frame = StyledFrame(targets_frame, bg="#353535")
            selector_frame.pack(fill="x", pady=2)

            # Get available targets
            targets = self.handler.get_available_targets()

            # Add browse option
            targets.append("─────────────────────")
            targets.append("🔍 Select another app...")

            # Combobox
            combo = ttk.Combobox(
                selector_frame,
                values=targets,
                width=30,
                font=("Arial", 9)
            )
            combo.pack(side="left", padx=2)

            # Set current value
            display_name = self.handler.get_display_name(selected_app)
            if display_name and display_name not in targets:
                # Add custom app to list
                targets.insert(-2, display_name)
                combo['values'] = targets

            combo.set(display_name if display_name else "❌ None")

            # Browse file function
            def on_browse_file():
                try:
                    file_path = filedialog.askopenfilename(
                        title="Select Application",
                        filetypes=[
                            ("Executable files", "*.exe"),
                            ("All files", "*.*")
                        ],
                        initialdir=os.path.expandvars(r"%ProgramFiles%")
                    )

                    if file_path:
                        exe_name = os.path.basename(file_path)
                        current_targets = list(combo['values'])

                        if exe_name not in current_targets:
                            current_targets.insert(-2, exe_name)
                            combo['values'] = current_targets

                        combo.set(exe_name)
                        combo.selection_clear()
                        combo.icursor(tk.END)
                        self.bindings_container.focus_set()
                        self._auto_save_binding(row_frame)

                except Exception as e:
                    log_error(e, "Error browsing for file")
                    messagebox.showerror("Error", f"Failed to select file: {str(e)}")

            # Selection change handler
            def on_combo_select(event):
                selected = combo.get()
                if selected == "🔍 Select another app...":
                    on_browse_file()
                    return

                # Handle duplicate check
                self._check_and_handle_duplicates(row_frame)
                self._auto_save_binding(row_frame)

            combo.bind('<<ComboboxSelected>>', on_combo_select)
            combo.bind('<FocusOut>', lambda e: self._auto_save_binding(row_frame))

            # Plus button (add another selector)
            plus_btn = tk.Button(
                selector_frame,
                text="+",
                command=lambda: self._add_another_selector(row_frame),
                bg="#2d5c2d",
                fg="white",
                font=("Arial", 10, "bold"),
                relief="flat",
                padx=6,
                pady=0,
                cursor="hand2",
                width=2
            )
            plus_btn.pack(side="left", padx=2)

            # Minus button (remove this selector)
            minus_btn = tk.Button(
                selector_frame,
                text="−",
                command=lambda: self._remove_target_selector(row_frame, selector_frame),
                bg="#5c1a1a",
                fg="white",
                font=("Arial", 10, "bold"),
                relief="flat",
                padx=6,
                pady=0,
                cursor="hand2",
                width=2
            )
            minus_btn.pack(side="left", padx=2)

            # Hover effects
            plus_btn.bind('<Enter>', lambda e: plus_btn.config(bg="#3d7d3d"))
            plus_btn.bind('<Leave>', lambda e: plus_btn.config(bg="#2d5c2d"))
            minus_btn.bind('<Enter>', lambda e: minus_btn.config(bg="#7d2424"))
            minus_btn.bind('<Leave>', lambda e: minus_btn.config(bg="#5c1a1a"))

            # Store references
            selector_frame.combo = combo
            selector_frame.minus_btn = minus_btn
            row_frame.target_selectors.append(selector_frame)

            # Update minus button visibility
            self._update_minus_button_visibility(row_frame)

        except Exception as e:
            log_error(e, "Error adding target selector")

    def _add_another_selector(self, row_frame):
        """Add another target selector to the row"""
        self._add_target_selector(row_frame, "None")

    def _remove_target_selector(self, row_frame, selector_frame):
        """Remove a target selector"""
        try:
            if len(row_frame.target_selectors) <= 1:
                messagebox.showwarning(
                    "Cannot Remove",
                    "At least one target selector must remain."
                )
                return

            # Remove from list
            row_frame.target_selectors.remove(selector_frame)
            selector_frame.destroy()

            # Update minus button visibility
            self._update_minus_button_visibility(row_frame)

            # Auto-save
            self._auto_save_binding(row_frame)

        except Exception as e:
            log_error(e, "Error removing target selector")

    def _update_minus_button_visibility(self, row_frame):
        """Update visibility of minus buttons based on selector count"""
        num_selectors = len(row_frame.target_selectors)

        for selector_frame in row_frame.target_selectors:
            if num_selectors <= 1:
                selector_frame.minus_btn.config(state="disabled")
            else:
                selector_frame.minus_btn.config(state="normal")

    def _auto_save_binding(self, row_frame):
        """Automatically save binding when changed"""
        try:
            var_name = row_frame.var_name

            # Collect all selected apps from target selectors
            selected_apps = []
            for selector_frame in row_frame.target_selectors:
                combo = selector_frame.combo
                display_value = combo.get()

                # Convert display name to internal name
                internal_name = self.handler.normalize_target_name(display_value)

                if internal_name and internal_name not in ["", "─", "Select another app"]:
                    selected_apps.append(internal_name)

            # Check for duplicates
            self._check_and_handle_duplicates(row_frame.var_name, selected_apps, row_frame)

            # Save to config
            if selected_apps:
                self.handler.save_variable_binding(var_name, selected_apps)
            else:
                self.handler.save_variable_binding(var_name, ["None"])

        except Exception as e:
            log_error(e, f"Error auto-saving binding for {row_frame.var_name}")

    def _check_and_handle_duplicates(self, current_var, selected_apps, current_row_frame):
        """Check for duplicate bindings and warn user"""
        try:
            for app_name in selected_apps:
                if self.handler.check_duplicate_binding(current_var, app_name):
                    messagebox.showwarning(
                        "Duplicate Binding",
                        f"'{app_name}' is already bound to another slider.\n\n"
                        f"This may cause unexpected behavior."
                    )
                    break

        except Exception as e:
            log_error(e, "Error checking duplicates")

    def _clear_binding(self, var_name, frame):
        """Clear binding and remove from UI"""
        try:
            # Clear from config
            self.handler.save_variable_binding(var_name, ["None"])

            # Remove from UI
            frame.destroy()
            del self.binding_rows[var_name]

        except Exception as e:
            log_error(e, f"Error clearing binding for {var_name}")

    def load_bindings(self, config=None):
        """Load bindings from config (called by config_tab)"""
        self._load_existing_bindings()
