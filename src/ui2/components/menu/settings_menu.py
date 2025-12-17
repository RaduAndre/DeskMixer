"""
Settings Menu Component
Handles general settings, layout configuration, and accent color.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from ui2 import colors
from ui2.settings_manager import settings_manager
from utils import system_startup

class SettingsMenu:
    def __init__(self, menu_builder):
        self.menu_builder = menu_builder

    def build_menu(self):
        """Build the settings menu content."""
        self.menu_builder.clear()
        
        self.menu_builder.add_head("General")
        
        # Start Hidden
        is_hidden = settings_manager.get_start_hidden() == 1
        item_hidden = self.menu_builder.add_item("Start Hidden (on tray)", selected=is_hidden)
        item_hidden.clicked.connect(lambda: self._toggle_setting_hidden(item_hidden))
        
        # Start on Startup
        is_startup = system_startup.check_startup_status()
        item_startup = self.menu_builder.add_item("Start on Windows startup", selected=is_startup)
        item_startup.clicked.connect(lambda: self._toggle_setting_startup(item_startup))
        
        # Slider Sampling
        sampling_item = self.menu_builder.add_item("Slider Sampling", is_expandable=True, selected=True)
        
        current_sampling = settings_manager.get_slider_sampling()
        
        instant_item = self.menu_builder.add_item("Instant", level=1, selected=(current_sampling == "instant"))
        responsive_item = self.menu_builder.add_item("Responsive", level=1, selected=(current_sampling == "responsive"))
        soft_item = self.menu_builder.add_item("Soft", level=1, selected=(current_sampling == "soft"))
        normal_item = self.menu_builder.add_item("Normal", level=1, selected=(current_sampling == "normal"))
        hard_item = self.menu_builder.add_item("Hard", level=1, selected=(current_sampling == "hard"))
        
        # Connect callbacks
        instant_item.clicked.connect(lambda: self._set_sampling("instant", instant_item, [responsive_item, soft_item, normal_item, hard_item]))
        responsive_item.clicked.connect(lambda: self._set_sampling("responsive", responsive_item, [instant_item, soft_item, normal_item, hard_item]))
        soft_item.clicked.connect(lambda: self._set_sampling("soft", soft_item, [instant_item, responsive_item, normal_item, hard_item]))
        normal_item.clicked.connect(lambda: self._set_sampling("normal", normal_item, [instant_item, responsive_item, soft_item, hard_item]))
        hard_item.clicked.connect(lambda: self._set_sampling("hard", hard_item, [instant_item, responsive_item, soft_item, normal_item]))
        
        self.menu_builder.add_head("Layout")
        # Grid Layout Section
        grid_item = self.menu_builder.add_item("Grid Size", is_expandable=True, selected=True)
        
        current_rows, current_cols = settings_manager.get_grid_dimensions()
        
        row_val = str(current_rows) if current_rows > 0 else ""
        col_val = str(current_cols) if current_cols > 0 else ""
        
        row_input = self.menu_builder.add_input_item("Rows (R)", initial_value=row_val, level=1, show_icon=False)
        col_input = self.menu_builder.add_input_item("Cols (C)", initial_value=col_val, level=1, show_icon=False)
        
        def validate_and_set_grid(val):
            # Check both inputs
            r_text = row_input.get_value()
            c_text = col_input.get_value()
            
            if r_text.isdigit() and c_text.isdigit():
                r = int(r_text)
                c = int(c_text)
                
                if r > 0 and c > 0:
                    # External validator check
                    if self.menu_builder.grid_validator:
                        if not self.menu_builder.grid_validator(r, c):
                            curr_r, curr_c = settings_manager.get_grid_dimensions()
                            if curr_r > 0: row_input.set_value(str(curr_r))
                            if curr_c > 0: col_input.set_value(str(curr_c))
                            
                            if hasattr(row_input, 'flash_error'): row_input.flash_error()
                            if hasattr(col_input, 'flash_error'): col_input.flash_error()
                            return

                    settings_manager.set_grid_dimensions(r, c)
                    if hasattr(self.menu_builder, 'on_grid_changed') and self.menu_builder.on_grid_changed:
                        self.menu_builder.on_grid_changed(r, c)
        
        row_input.value_changed.connect(validate_and_set_grid)
        col_input.value_changed.connect(validate_and_set_grid)
        
        # --- Accent Color Element ---
        color_item = self.menu_builder.add_item("Accent Color", is_expandable=True)
        
        # Check current accent
        current_accent = settings_manager.get_accent_color()
        if not current_accent: current_accent = "teal" # fallback
        
        TEAL_HEX = "#00EAD0"
        is_default = (current_accent.lower() == "teal" or current_accent.upper() == TEAL_HEX)
        
        # 1. Default (Default arg for teal)
        default_item = self.menu_builder.add_item("Default", level=1, selected=is_default)
        default_item.color_id = "teal" 
        
        all_color_items = [default_item]
        
        # 2. Custom Color Item (Only if active and not default)
        if not is_default:
            custom_hex_item = self.menu_builder.add_item(current_accent.upper(), level=1, selected=True)
            custom_hex_item.color_id = current_accent
            all_color_items.append(custom_hex_item)
        
        # 3. Select new color
        custom_item = self.menu_builder.add_item("Select new color...", level=1, selected=False)
        all_color_items.append(custom_item)
        
        # Connect
        default_item.clicked.connect(lambda: self.menu_builder._set_accent(default_item, all_color_items))
        custom_item.clicked.connect(lambda: self.menu_builder._open_color_picker(custom_item, all_color_items))

        # Reorder Section
        reorder_item = self.menu_builder.add_item("Reorder Elements", is_expandable=True)
        
        reorder_btns = self.menu_builder.add_item("Swap Buttons", level=1)
        reorder_sliders = self.menu_builder.add_item("Swap Sliders", level=1)
        
        # Set selection state based on MenuBuilder's mode flags
        if self.menu_builder.reorder_sliders_mode:
             reorder_sliders.set_selected(True)
        if self.menu_builder.reorder_buttons_mode:
             reorder_btns.set_selected(True)
        
        def toggle_reorder_buttons():
            if hasattr(self.menu_builder, 'on_reorder_buttons_toggled'):
                 active = not reorder_btns.is_selected() # Toggle
                 reorder_btns.set_selected(active)
                 if active:
                     reorder_sliders.set_selected(False)
                     if hasattr(self.menu_builder, 'on_reorder_sliders_toggled'):
                         self.menu_builder.on_reorder_sliders_toggled(False)
                         
                 self.menu_builder.on_reorder_buttons_toggled(active)

        def toggle_reorder_sliders():
            if hasattr(self.menu_builder, 'on_reorder_sliders_toggled'):
                 active = not reorder_sliders.is_selected()
                 reorder_sliders.set_selected(active)
                 if active:
                     reorder_btns.set_selected(False)
                     if hasattr(self.menu_builder, 'on_reorder_buttons_toggled'):
                         self.menu_builder.on_reorder_buttons_toggled(False)
                 
                 self.menu_builder.on_reorder_sliders_toggled(active)

        reorder_btns.clicked.connect(toggle_reorder_buttons)
        reorder_sliders.clicked.connect(toggle_reorder_sliders)

        # Add Version Label
        self.menu_builder.content_layout.addStretch()
        
        version_text = "DeskMixer build unknown"
        if hasattr(self.menu_builder, 'version') and self.menu_builder.version:
            version_text = f"DeskMixer v{self.menu_builder.version}"
        
        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(f"color: {colors.WHITE}; margin-top: 10px; margin-bottom: 0px;")
        self.menu_builder.content_layout.addWidget(version_label)

    def _toggle_setting_hidden(self, item):
        new_val = 0 if settings_manager.get_start_hidden() == 1 else 1
        settings_manager.set_start_hidden(new_val)
        item.set_selected(new_val == 1)

    def _toggle_setting_startup(self, item):
        current_status = system_startup.check_startup_status()
        new_val = not current_status
        success = system_startup.set_startup(new_val)
        
        if success:
             item.set_selected(new_val)
        else:
             print("Failed to change startup settings")
             if hasattr(item, 'flash_error'):
                 item.flash_error()

    def _set_sampling(self, mode, selected_item, other_items):
        settings_manager.set_slider_sampling(mode)
        selected_item.set_selected(True)
        for item in other_items:
            item.set_selected(False)
            
        if self.menu_builder.audio_manager:
            self.menu_builder.audio_manager.set_slider_sampling(mode)
