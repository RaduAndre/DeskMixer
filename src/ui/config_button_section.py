# ui/config_button_section.py
import tkinter as tk
from tkinter import ttk, messagebox
from utils.error_handler import log_error


class ConfigButtonSection:
    """Handles the Button Bindings UI and logic."""

    def __init__(self, parent_frame, audio_manager, config_manager, common_helpers):
        self.audio_manager = audio_manager
        self.config_manager = config_manager
        self.helpers = common_helpers
        self.button_binding_rows = []
        
        self.button_canvas = None
        self.button_container = None

        self._create_ui(parent_frame)

    def _create_ui(self, parent):
        """Create button bindings section"""
        try:
            button_frame = tk.LabelFrame(
                parent,
                text="Button Bindings (b1, b2, b3...) - Actions",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=10,
                pady=10
            )
            # Assuming caller (ConfigTab) will grid this.
            button_frame.grid_rowconfigure(1, weight=1)
            button_frame.grid_columnconfigure(0, weight=1)

            # Help text
            help_text = tk.Label(
                button_frame,
                text="Bind serial buttons to actions: Play/Pause, Mute, Next Track, Volume Up/Down, Custom Keybinds, etc.",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 8),
                wraplength=850,
                justify="left"
            )
            help_text.grid(row=0, column=0, sticky="ew", pady=(0, 5))

            # Scrollable container with responsive canvas
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

            # Mouse wheel scrolling - bind only to canvas and container
            def _on_mousewheel(event):
                self.button_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
            self.button_canvas.bind("<Enter>", lambda e: self.button_canvas.bind_all("<MouseWheel>", _on_mousewheel))
            self.button_canvas.bind("<Leave>", lambda e: self.button_canvas.unbind_all("<MouseWheel>"))
            self.button_container.bind("<Enter>", lambda e: self.button_canvas.bind_all("<MouseWheel>", _on_mousewheel))
            self.button_container.bind("<Leave>", lambda e: self.button_canvas.unbind_all("<MouseWheel>"))

            # Add button
            btn_container = tk.Frame(button_frame, bg="#2d2d2d")
            btn_container.grid(row=2, column=0, sticky="ew", pady=5)
            btn_container.grid_columnconfigure(0, weight=1)

            add_button_btn = tk.Button(
                btn_container,
                text="➕ Add Button Binding",
                command=self._add_button_binding_row,
                bg="#404040",
                fg="white",
                font=("Arial", 9, "bold"),
                relief="flat",
                padx=10,
                pady=5,
                cursor="hand2"
            )
            add_button_btn.grid(row=0, column=0)
            
            self.frame = button_frame

        except Exception as e:
            log_error(e, "Error creating button section")
            
    def load_bindings(self, config):
        """Load bindings from config and create UI rows."""
        for button_name, binding in config.get('button_bindings', {}).items():
            if isinstance(binding, dict):
                action = binding.get('action', '')
                target = binding.get('target', '')
                keybind = binding.get('keybind', '')
                app_path = binding.get('app_path', '')
            else:
                # Handle legacy format where binding was just the action
                action = binding
                target = ''
                keybind = ''
                app_path = ''

            # Only add valid button bindings
            if button_name and action:
                self._add_button_binding_row(
                    button_name=button_name,
                    action=action,
                    target=target,
                    keybind=keybind,
                    app_path=app_path
                )

    def _auto_save_button_binding(self, button_entry, action_combo, target_combo, keybind_entry, app_path_entry):
        """Automatically save button binding when changes occur."""
        try:
            button_name = button_entry.get().strip()
            action = self.helpers.normalize_action_name(action_combo.get().strip())

            # Skip if button name is empty or invalid format
            if not button_name or not button_name.startswith('b'):
                return False

            # Target is only relevant for "mute" action, and only if the combo is mapped
            target = None
            if action == "mute" and target_combo.winfo_ismapped():
                target = self.helpers.normalize_target_name(target_combo.get().strip())
            
            # Keybind is only relevant for "keybind" action, and only if the entry is mapped
            keybind = None
            if action == "keybind" and keybind_entry.winfo_ismapped():
                 keybind = keybind_entry.get().strip()
            
            # App path is only relevant for "launch_app" action, and only if the entry is mapped
            app_path = None
            if action == "launch_app" and app_path_entry.winfo_ismapped():
                app_path = app_path_entry.get().strip()
            
            # Prepare binding data
            binding_data = {
                'action': action,
                'target': target if target and target != "None" else None,
                'keybind': keybind if keybind else None,
                'app_path': app_path if app_path else None
            }

            # Save binding
            if self.config_manager.add_button_binding(button_name, binding_data):
                return True
            
            return False

        except Exception as e:
            log_error(e, "Error auto-saving button binding")
            return False

    def _add_button_binding_row(self, button_name="", action="", target="", keybind="", app_path=""):
        """Add a button binding row with responsive layout"""
        try:
            row_frame = tk.Frame(self.button_container, bg="#353535", padx=6, pady=4)
            row_frame.pack(fill="x", padx=3, pady=2)

            # Use grid for better control
            row_frame.grid_columnconfigure(1, weight=0)
            row_frame.grid_columnconfigure(3, weight=0)
            row_frame.grid_columnconfigure(5, weight=1)

            # Button name
            tk.Label(
                row_frame,
                text="Button (bX):",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            ).grid(row=0, column=0, padx=2, sticky="w")

            button_entry = tk.Entry(row_frame, width=8, font=("Arial", 9))
            button_entry.insert(0, button_name)
            button_entry.grid(row=0, column=1, padx=2, sticky="w")

            tk.Label(
                row_frame,
                text="→",
                bg="#353535",
                fg="#00ff00",
                font=("Arial", 10, "bold")
            ).grid(row=0, column=2, padx=2)

            # Action dropdown
            tk.Label(
                row_frame,
                text="Action:",
                bg="#353535",
                fg="white",
                font=("Arial", 9)
            ).grid(row=0, column=3, padx=2, sticky="w")

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
            action_combo.grid(row=0, column=4, padx=2, sticky="w")

            if action:
                display_action = self.helpers.get_action_display_name(action)
                if display_action in actions:
                    action_combo.set(display_action)

            # Dynamic elements container
            dynamic_frame = tk.Frame(row_frame, bg="#353535")
            dynamic_frame.grid(row=0, column=5, padx=2, sticky="ew")

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

            # BIND AUTO-SAVE TO ALL ENTRIES
            button_entry.bind('<FocusOut>', 
                lambda e: self._auto_save_button_binding(
                    button_entry, action_combo, target_combo, keybind_entry, app_path_entry
                )
            )
            
            target_combo.bind('<<ComboboxSelected>>', 
                lambda e: self._auto_save_button_binding(
                    button_entry, action_combo, target_combo, keybind_entry, app_path_entry
                )
            )
            
            keybind_entry.bind('<FocusOut>', 
                lambda e: self._auto_save_button_binding(
                    button_entry, action_combo, target_combo, keybind_entry, app_path_entry
                )
            )
            
            app_path_entry.bind('<FocusOut>', 
                lambda e: self._auto_save_button_binding(
                    button_entry, action_combo, target_combo, keybind_entry, app_path_entry
                )
            )

            # Show/hide elements based on action
            def on_action_change(event=None):
                # Clear dynamic frame
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

            # BIND AUTO-SAVE TO ACTION COMBO AND CALL on_action_change
            action_combo.bind('<<ComboboxSelected>>', 
                lambda e: (on_action_change(e), self._auto_save_button_binding(
                    button_entry, action_combo, target_combo, keybind_entry, app_path_entry
                ))
            )

            on_action_change()  # Initial state

            # Button container
            btn_frame = tk.Frame(row_frame, bg="#353535")
            btn_frame.grid(row=0, column=6, padx=2, sticky="e")

            # Test button
            test_btn = tk.Button(
                btn_frame,
                text="▶️",
                command=lambda: self._test_button_action(
                    self.helpers.normalize_action_name(action_var.get()),
                    self.helpers.normalize_target_name(target_var.get()) if target_var.get() else "",
                    keybind_entry.get(),
                    app_path_entry.get()
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

            # Delete button
            delete_btn = tk.Button(
                btn_frame,
                text="🗑",
                command=lambda: self._delete_button_binding(button_entry.get(), row_frame),
                bg="#5c1a1a",
                fg="white",
                font=("Arial", 9),
                relief="flat",
                padx=5,
                pady=2,
                cursor="hand2"
            )
            delete_btn.pack(side="left", padx=1)

            self.button_binding_rows.append(row_frame)

        except Exception as e:
            log_error(e, "Error adding button binding row")
            
    def _test_button_action(self, action, target, keybind, app_path):
        """Test a button action"""
        try:
            from utils.actions import ActionHandler # Assuming this import is correct

            action_handler = ActionHandler(self.audio_manager)

            kwargs = {}
            if action == "mute" and target:
                kwargs['target'] = target
            elif action == "keybind" and keybind:
                kwargs['keys'] = keybind
            elif action == "launch_app" and app_path:
                kwargs['app_path'] = app_path

            success = action_handler.execute_action(action, **kwargs)

            if success:
                messagebox.showinfo("Test", f"Action '{action}' executed successfully!")
            else:
                messagebox.showwarning("Test", f"Action '{action}' failed to execute")

        except Exception as e:
            messagebox.showerror("Error", f"Error testing button action: {str(e)}")
            log_error(e, "Error testing button action")

    def _delete_button_binding(self, button_name, frame):
        """Delete a button binding"""
        try:
            if button_name:
                self.config_manager.remove_button_binding(button_name)
            frame.destroy()
            if frame in self.button_binding_rows:
                self.button_binding_rows.remove(frame)

        except Exception as e:
            log_error(e, "Error deleting button binding")