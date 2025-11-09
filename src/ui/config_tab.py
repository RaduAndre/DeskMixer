# ui/config_tab.py (MODIFIED)
import tkinter as tk
from tkinter import ttk, messagebox
# serial.tools.list_ports is no longer needed here, moved to ConfigSerialSection
from config.config_manager import ConfigManager
from serial_comm.serial_handler import SerialHandler  # Still needed for serial_handler object
from utils.error_handler import handle_error, log_error

# NEW IMPORTS
from ui.utils.ui_helpers import UIHelpers
from ui.handlers.serial_section_handler import SerialSectionHandler
from ui.sections.serial_section_ui import SerialSectionUI
from ui.config_bindings_section import ConfigBindingsSection
from ui.config_button_section import ConfigButtonSection


class ConfigTab:
    """Configuration tab UI - now an orchestrator for its sections."""

    def __init__(self, parent, audio_manager):
        self.audio_manager = audio_manager
        self.frame = tk.Frame(parent, bg="#1e1e1e")
        self.config_manager = ConfigManager()
        self.serial_handler = SerialHandler(config_manager=self.config_manager)
        self.unsaved_changes = False  # Keep unsaved_changes for older checks

        # NEW: Initialize helpers
        self.helpers = UIHelpers(self.audio_manager, self.config_manager)

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

            # Serial Port Section - REFACTORED
            serial_handler = SerialSectionHandler(
                self.serial_handler,
                self.config_manager
            )
            self.serial_section = SerialSectionUI(
                main_container,
                serial_handler
            )
            self.serial_section.frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

            # Variable Bindings Section - NOW PASSES SERIAL_HANDLER
            self.bindings_section = ConfigBindingsSection(
                main_container,
                self.audio_manager,
                self.config_manager,
                self.helpers,
                self.serial_handler  # Pass serial_handler for auto-configuration
            )
            self.bindings_section.frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

            # Button Bindings Section - NOW PASSES SERIAL_HANDLER
            self.button_section = ConfigButtonSection(
                main_container,
                self.audio_manager,
                self.config_manager,
                self.helpers,
                self.serial_handler  # Pass serial_handler for auto-configuration
            )
            self.button_section.frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)


        except Exception as e:
            handle_error(e, "Failed to create config tab UI")

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

        except Exception as e:
            log_error(e, "Error loading configuration")