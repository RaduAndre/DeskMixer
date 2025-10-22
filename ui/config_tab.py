# ui/config_tab.py (MODIFIED)
import tkinter as tk
from tkinter import ttk, messagebox
# serial.tools.list_ports is no longer needed here, moved to ConfigSerialSection
from config.config_manager import ConfigManager
from serial_comm.serial_handler import SerialHandler # Still needed for serial_handler object
from utils.error_handler import handle_error, log_error

# NEW IMPORTS
from ui.config_helpers import ConfigHelpers
from ui.config_serial_section import ConfigSerialSection
from ui.config_bindings_section import ConfigBindingsSection
from ui.config_button_section import ConfigButtonSection


class ConfigTab:
    """Configuration tab UI - now an orchestrator for its sections."""

    def __init__(self, parent, audio_manager):
        self.audio_manager = audio_manager
        self.frame = tk.Frame(parent, bg="#1e1e1e")
        self.config_manager = ConfigManager()
        self.serial_handler = SerialHandler() # Still instantiate here
        self.unsaved_changes = False # Keep unsaved_changes for older checks

        # NEW: Initialize helpers
        self.helpers = ConfigHelpers(self.audio_manager, self.config_manager)

        # Initialize section objects
        self.serial_section = None
        self.bindings_section = None
        self.button_section = None

        # Configure frame to be responsive
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._create_ui()
        self._load_config()

        # Attempt auto-connect (now delegated)
        if self.serial_section:
            self.serial_section.auto_connect()

        # Bind resize event
        self.frame.bind('<Configure>', self._on_resize)

        self.audio_manager.set_handlers(self.serial_handler, self.config_manager)

    # _auto_connect removed: moved to ConfigSerialSection.auto_connect

    def _on_resize(self, event):
        """Handle window resize events"""
        try:
            # Adjust canvas heights based on available space
            available_height = event.height
            # Check for the existence of the section objects and their canvas attributes
            if self.bindings_section and hasattr(self.bindings_section, 'bindings_canvas'):
                self.bindings_section.bindings_canvas.configure(height=min(200, available_height // 3))
            if self.button_section and hasattr(self.button_section, 'button_canvas'):
                self.button_section.button_canvas.configure(height=min(200, available_height // 3))
        except Exception:
            # Pass silently on resize errors for robustness
            pass

    def _create_ui(self):
        """Create the configuration UI"""
        try:
            # Main container with grid layout for better responsiveness
            main_container = tk.Frame(self.frame, bg="#1e1e1e")
            main_container.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

            # Configure grid weights for responsiveness
            main_container.grid_rowconfigure(0, weight=0)  # Serial section
            main_container.grid_rowconfigure(1, weight=1)  # Bindings section
            main_container.grid_rowconfigure(2, weight=1)  # Button section
            main_container.grid_columnconfigure(0, weight=1)

            # Serial Port Section
            self.serial_section = ConfigSerialSection(
                main_container,
                self.serial_handler,
                self.config_manager
            )
            self.serial_section.frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)


            # Variable Bindings Section
            self.bindings_section = ConfigBindingsSection(
                main_container,
                self.audio_manager,
                self.config_manager,
                self.helpers
            )
            self.bindings_section.frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)


            # Button Bindings Section
            self.button_section = ConfigButtonSection(
                main_container,
                self.audio_manager,
                self.config_manager,
                self.helpers
            )
            self.button_section.frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)


        except Exception as e:
            handle_error(e, "Failed to create config tab UI")

    # _create_serial_section removed: moved to ConfigSerialSection
    # _create_bindings_section removed: moved to ConfigBindingsSection
    # _create_button_section removed: moved to ConfigButtonSection
    # _get_available_actions and helpers methods removed: moved to ConfigHelpers
    # _auto_save_button_binding, _add_button_binding_row, _test_button_action, _delete_button_binding removed: moved to ConfigButtonSection
    # _get_available_targets, _normalize_target_name, _get_display_name removed: moved to ConfigHelpers
    # _add_binding_row removed: moved to ConfigBindingsSection

    def _refresh_all_app_lists(self):
        """Refresh all app dropdowns in the binding rows and button rows"""
        try:
            targets = self.helpers.get_available_targets()
            
            # 1. Refresh Variable Bindings
            if self.bindings_section:
                # Update all comboboxes in bindings
                for widget in self.bindings_section.bindings_container.winfo_children():
                    if isinstance(widget, tk.Frame):
                        for child in widget.grid_slaves():
                            if child.grid_info().get("column") == 4 and isinstance(child, ttk.Combobox):
                                current_value = child.get()
                                child['values'] = targets
                                if current_value in targets:
                                    child.set(current_value)

            # 2. Refresh Button Bindings (Mute target comboboxes)
            if self.button_section:
                # The target combo is inside dynamic_frame which is inside the row_frame (widget)
                for row_frame in self.button_section.button_container.winfo_children():
                    if isinstance(row_frame, tk.Frame):
                        # Find the dynamic_frame (column 5)
                        for dynamic_frame in row_frame.grid_slaves(column=5):
                            if isinstance(dynamic_frame, tk.Frame):
                                # Find the Combobox inside dynamic_frame
                                for subchild in dynamic_frame.winfo_children():
                                    if isinstance(subchild, ttk.Combobox):
                                        current_value = subchild.get()
                                        subchild['values'] = targets
                                        if current_value in targets:
                                            subchild.set(current_value)


            messagebox.showinfo("Refreshed", "All application lists updated!")

        except Exception as e:
            log_error(e, "Error refreshing all app lists")

    # _show_mode_tooltip and _hide_tooltip removed: was not used in the original code, can be added back later if needed.
    # _save_binding removed: replaced by auto-save logic in ConfigBindingsSection
    # _toggle_serial removed: moved to ConfigSerialSection
    # _refresh_ports removed: moved to ConfigSerialSection


    def _load_config(self):
        """Load configuration from file and pass to sections"""
        try:
            config = self.config_manager.load_config()

            # Load variable bindings
            if self.bindings_section:
                self.bindings_section.load_bindings(config)

            # Load button bindings
            if self.button_section:
                self.button_section.load_bindings(config)

            # Load last connected port (delegated to serial section)
            if self.serial_section:
                # The serial section loads this in its __init__, 
                # but we'll keep the variables updated for safety if needed.
                last_port = config.get('last_connected_port')
                last_baud = config.get('last_connected_baud', "9600")
                if last_port:
                    self.serial_section.com_port_var.set(last_port)
                    self.serial_section.baud_var.set(last_baud)

        except Exception as e:
            log_error(e, "Error loading configuration")

    # _auto_save_binding removed: moved to ConfigBindingsSection
    # _delete_binding removed: moved to ConfigBindingsSection
    # _check_duplicate_binding removed: moved to ConfigHelpers