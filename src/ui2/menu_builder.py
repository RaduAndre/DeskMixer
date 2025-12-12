"""
Menu builder for constructing menu content dynamically.
"""

import sys
import os
import re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from ui2.components.menu_item import MenuItem
from ui2.components.section_header import SectionHeader
from ui2 import colors, fonts
from ui2.components.input_item import InputItem
from ui2.components.browse_item import BrowseItem
from ui2.settings_manager import settings_manager
from ui2.icon_manager import icon_manager # For consistent action names if needed
from utils import system_startup
from PySide6.QtWidgets import QFileDialog, QMenu
from PySide6.QtGui import QAction, QCursor

try:
    import win32com.client
except ImportError:
    win32com = None



class MenuBuilder:
    """Helper class for building menu content."""
    
    def __init__(self, content_layout: QVBoxLayout, audio_manager=None):
        self.content_layout = content_layout
        self.audio_manager = audio_manager
        self.menu_items = []
        self.sections = {}  # Track sections and their items
        self.current_section = None
        self.current_parent_item = None # Track current expandable parent (level 0)
        self.item_containers = {} # Map parent item -> sub-container
        self.parent_map = {} # Map sub-item -> parent item
        self.default_children = {} # Map parent item -> default child item
        self.variable_validator = None # Callback(value, argument, exclude_obj) -> conflicting_obj
        self.grid_validator = None # Callback(rows, cols) -> bool
    
    def clear(self):
        """Clear all menu content."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.menu_items.clear()
        self.sections.clear()
        self.current_section = None
        self.current_parent_item = None
        self.item_containers.clear()
        self.parent_map.clear()
        self.default_children.clear()
    
    def add_head(self, text: str, expandable: bool = False, expanded: bool = True):
        """Add a menu section head."""
        # Add separator line ABOVE the heading (but not for the first section)
        if self.content_layout.count() > 0:
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"""
                QFrame {{
                    background-color: {colors.BACKGROUND};
                    border: none;
                    min-height: 1px;
                    max-height: 1px;
                    margin-top: 0px;
                    margin-bottom: 5px;
                }}
            """)
            self.content_layout.addWidget(line)
        
        # Create section header
        header = SectionHeader(text, expandable=expandable, expanded=expanded)
        self.content_layout.addWidget(header)
        
        # Create section container for items
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        self.content_layout.addWidget(container)
        
        # Store section info
        self.current_section = text
        self.sections[text] = {
            'header': header,
            'container': container,
            'layout': container_layout,
            'items': [],
            'expanded': expanded,
            'anim': None  # Placeholder for animation object
        }
        
        # Initial state
        if not expanded:
            container.setMaximumHeight(0)
            container.hide()
        
        # Connect header click to toggle function
        if expandable:
            header.clicked.connect(lambda: self.toggle_section(text))
    
    def add_item(self, text: str, level: int = 0, selected: bool = False, 
                 is_expandable: bool = False, is_default: bool = False, extra_margin: int = 0, on_right_click=None, callback=None) -> MenuItem:
        """Add a menu item."""
        item = MenuItem(text, level=level, selected=selected, is_expandable=is_expandable, is_default=is_default, extra_margin=extra_margin, on_right_click=on_right_click)
        
        # Connect internal toggle signal for expandable items
        if is_expandable:
            item.toggled.connect(lambda expanded: self.toggle_item_expand(item, expanded))
            # Also handle body click -> activate default child
            item.clicked.connect(lambda: self.activate_default_child(item))
        elif callback:
            # Normal item click
            item.clicked.connect(callback)
            
        # Determine where to add the item
        target_layout = self.content_layout
        
        if level == 0:
            # Level 0 items go to section container
            if self.current_section and self.current_section in self.sections:
                target_layout = self.sections[self.current_section]['layout']
                self.sections[self.current_section]['items'].append(item)
            
            # Reset current parent if this is a new level 0 item
            self.current_parent_item = item if is_expandable else None
            
            # If expandable, create a sub-container for potential children
            if is_expandable:
                sub_container = QWidget()
                sub_container.setStyleSheet("background: transparent;")
                sub_layout = QVBoxLayout(sub_container)
                sub_layout.setContentsMargins(0, 0, 0, 0)
                sub_layout.setSpacing(0)
                sub_container.setMaximumHeight(0) # Start collapsed
                sub_container.hide()
                
                # Add item then container
                target_layout.addWidget(item)
                target_layout.addWidget(sub_container)
                
                self.item_containers[item] = {
                    'container': sub_container,
                    'layout': sub_layout,
                    'items': [],
                    'anim': None
                }
                
                # We already added widgets, so don't use target_layout.addWidget(item) again below
                self.menu_items.append(item)
                return item
                
        elif level == 1:
            # Level 1 items go to current parent's container
            if self.current_parent_item and self.current_parent_item in self.item_containers:
                target_layout = self.item_containers[self.current_parent_item]['layout']
                self.item_containers[self.current_parent_item]['items'].append(item)
                self.parent_map[item] = self.current_parent_item
                
                # Register as default if needed
                if is_default:
                   self.default_children[self.current_parent_item] = item
            else:
                # Fallback if no parent (shouldn't happen with correct usage)
                pass

        target_layout.addWidget(item)
        self.menu_items.append(item)
        
        # FIX: If item is initialized as selected and has a parent, update parent state immediately
        if level == 1 and selected and self.current_parent_item:
            self.current_parent_item.set_has_active_child(True)
            
        return item
    
    
    def add_input_item(self, placeholder: str, initial_value: str = "", level: int = 0, show_icon: bool = True, icon_name: str = "record.svg", icon_callback=None, callback=None) -> InputItem:
        """Add an input menu item."""
        item = InputItem(placeholder, initial_value, level=level, show_icon=show_icon, icon_name=icon_name, icon_callback=icon_callback)
        
        if callback:
            item.value_changed.connect(callback)
            
        target_layout = self.content_layout
        
        if level == 1:
            if self.current_parent_item and self.current_parent_item in self.item_containers:
                target_layout = self.item_containers[self.current_parent_item]['layout']
                self.item_containers[self.current_parent_item]['items'].append(item)
                
                # Register as default child (so parent click activates it)
                self.default_children[self.current_parent_item] = item
        
        target_layout.addWidget(item)
        self.menu_items.append(item) # Add to global list for deselect loop
        return item
        
    def add_browse_item(self, initial_value: str = "", level: int = 0) -> BrowseItem:
        """Add a browse menu item."""
        item = BrowseItem(initial_value=initial_value, level=level)
        
        target_layout = self.content_layout
        if level == 1:
            if self.current_parent_item and self.current_parent_item in self.item_containers:
                target_layout = self.item_containers[self.current_parent_item]['layout']
                self.item_containers[self.current_parent_item]['items'].append(item)
                
                # Register as default child
                self.default_children[self.current_parent_item] = item
        
        target_layout.addWidget(item)
        self.menu_items.append(item)
        return item
    
    def build_settings_menu(self):
        """Build the settings menu content."""
        self.clear()
        
        self.add_head("General")
        
        # Start Hidden
        is_hidden = settings_manager.get_start_hidden() == 1
        item_hidden = self.add_item("Start Hidden (on tray)", selected=is_hidden)
        item_hidden.clicked.connect(lambda: self._toggle_setting_hidden(item_hidden))
        
        # Start on Startup
        is_startup = system_startup.check_startup_status()
        item_startup = self.add_item("Start on Windows startup", selected=is_startup)
        item_startup.clicked.connect(lambda: self._toggle_setting_startup(item_startup))
        
        # Slider Sampling
        sampling_item = self.add_item("Slider Sampling", is_expandable=True, selected=True)
        
        current_sampling = settings_manager.get_slider_sampling()
        
        instant_item = self.add_item("Instant", level=1, selected=(current_sampling == "instant"))
        
        responsive_item = self.add_item("Responsive", level=1, selected=(current_sampling == "responsive"))
        
        soft_item = self.add_item("Soft", level=1, selected=(current_sampling == "soft"))
        
        normal_item = self.add_item("Normal", level=1, selected=(current_sampling == "normal"))
        
        hard_item = self.add_item("Hard", level=1, selected=(current_sampling == "hard"))
        
        # Connect callbacks
        instant_item.clicked.connect(lambda: self._set_sampling("instant", instant_item, [responsive_item, soft_item, normal_item, hard_item]))
        responsive_item.clicked.connect(lambda: self._set_sampling("responsive", responsive_item, [instant_item, soft_item, normal_item, hard_item]))
        soft_item.clicked.connect(lambda: self._set_sampling("soft", soft_item, [instant_item, responsive_item, normal_item, hard_item]))
        normal_item.clicked.connect(lambda: self._set_sampling("normal", normal_item, [instant_item, responsive_item, soft_item, hard_item]))
        hard_item.clicked.connect(lambda: self._set_sampling("hard", hard_item, [instant_item, responsive_item, soft_item, normal_item]))
        
        self.add_head("Layout")
        # Grid Layout Section
        grid_item = self.add_item("Grid Size", is_expandable=True, selected=True)
        
        current_rows, current_cols = settings_manager.get_grid_dimensions()
        # Default display if 0 (auto) -> maybe show empty or 0? 
        # User request: "input the number of columns as C and rows as R"
        
        row_val = str(current_rows) if current_rows > 0 else ""
        col_val = str(current_cols) if current_cols > 0 else ""
        
        row_input = self.add_input_item("Rows (R)", initial_value=row_val, level=1, show_icon=False)
        col_input = self.add_input_item("Cols (C)", initial_value=col_val, level=1, show_icon=False)
        
        def validate_and_set_grid(val):
            # Check both inputs
            r_text = row_input.get_value()
            c_text = col_input.get_value()
            
            if r_text.isdigit() and c_text.isdigit():
                r = int(r_text)
                c = int(c_text)
                
                if r > 0 and c > 0:
                    # External validator check (e.g. check against button count)
                    if self.grid_validator:
                        if not self.grid_validator(r, c):
                            # Invalid: Revert to current settings
                            # To avoid visual glitching, might wait? 
                            # But we need to reject.
                            # Revert UI to match actual settings
                            curr_r, curr_c = settings_manager.get_grid_dimensions()
                            # Prevent infinite loop if setting value triggers change again (InputItem usually doesn't if logic checks change)
                            # But safe to just reset.
                            if curr_r > 0: row_input.set_value(str(curr_r))
                            if curr_c > 0: col_input.set_value(str(curr_c))
                            
                            # Flash Error
                            if hasattr(row_input, 'flash_error'): row_input.flash_error()
                            if hasattr(col_input, 'flash_error'): col_input.flash_error()
                            
                            return

                    settings_manager.set_grid_dimensions(r, c)
                    # Notify update?
                    if hasattr(self, 'on_grid_changed') and self.on_grid_changed:
                        self.on_grid_changed(r, c)
        
        row_input.value_changed.connect(validate_and_set_grid)
        col_input.value_changed.connect(validate_and_set_grid)
        
        # Reorder Section
        reorder_item = self.add_item("Reorder Elements", is_expandable=True)
        
        reorder_btns = self.add_item("Swap Buttons", level=1)
        reorder_sliders = self.add_item("Swap Sliders", level=1)
        
        # Toggle behavior for reorder buttons
        # We need a way to show active state. 
        # Since these are actions, we can use 'selected' state to indicate active mode.
        # But we need to sync with MainWindow state if possible.
        # For now, simplistic toggle callback.
        
        def toggle_reorder_buttons():
            # Signal main window to enter/exit reorder mode
            if hasattr(self, 'on_reorder_buttons_toggled'):
                 active = not reorder_btns.is_selected() # Toggle
                 reorder_btns.set_selected(active)
                 # Disable other reorder mode if needed? User didn't specify exclusivity but usually good.
                 if active:
                     reorder_sliders.set_selected(False)
                     if hasattr(self, 'on_reorder_sliders_toggled'):
                         self.on_reorder_sliders_toggled(False)
                         
                 self.on_reorder_buttons_toggled(active)

        def toggle_reorder_sliders():
            if hasattr(self, 'on_reorder_sliders_toggled'):
                 active = not reorder_sliders.is_selected()
                 reorder_sliders.set_selected(active)
                 if active:
                     reorder_btns.set_selected(False)
                     if hasattr(self, 'on_reorder_buttons_toggled'):
                         self.on_reorder_buttons_toggled(False)
                 
                 self.on_reorder_sliders_toggled(active)

        reorder_btns.clicked.connect(toggle_reorder_buttons)
        reorder_sliders.clicked.connect(toggle_reorder_sliders)

        # Add Version Label
        self.content_layout.addStretch()
        
        version_text = "DeskMixer build unknown"
        # Use version from main.py if available
        if hasattr(self, 'version') and self.version:
            version_text = f"DeskMixer v{self.version}"
        
        version_label = QLabel(version_text)
        version_label.setAlignment(Qt.AlignCenter)
        # Final Style: White color
        version_label.setStyleSheet("color: white; margin-top: 10px; margin-bottom: 0px;")
        self.content_layout.addWidget(version_label)
        
    def _toggle_setting_hidden(self, item):
        new_val = 0 if settings_manager.get_start_hidden() == 1 else 1
        settings_manager.set_start_hidden(new_val)
        item.set_selected(new_val == 1)

    def _toggle_setting_startup(self, item):
        # Initial check
        current_status = system_startup.check_startup_status()
        new_val = not current_status
        
        # specific for system_startup which returns success bool
        success = system_startup.set_startup(new_val)
        
        if success:
             # Just invert selection if success
             # Double check status or just trust? 
             # Trusting set_startup logic or re-checking?
             # Re-checking is safer but might be overkill.
             # Let's just update UI based on intent if success.
             item.set_selected(new_val)
        else:
             # Failed? Maybe flash error?
             print("Failed to change startup settings")
             if hasattr(item, 'flash_error'):
                 item.flash_error()

    # Removed _set_alignment helper as it's no longer used

    def _set_sampling(self, mode, selected_item, other_items):
        settings_manager.set_slider_sampling(mode)
        selected_item.set_selected(True)
        for item in other_items:
            item.set_selected(False)
            
        # Update live variable in AudioManager as requested
        if self.audio_manager:
            self.audio_manager.set_slider_sampling(mode)
    
    def build_slider_menu(self, target_slider):
        """Build the slider configuration menu content."""
        self.clear()
        
        # Helper to create toggleable item
        def add_toggle_item(name, value, argument=None, level=0, extra_margin=0, on_right_click=None, parent=None):
            is_selected = target_slider.has_variable(value, argument)
            item = self.add_item(name, level=level, selected=is_selected, extra_margin=extra_margin, on_right_click=on_right_click)
            # Custom click handler for toggle
            item.clicked.connect(lambda: self._handle_slider_toggle(item, target_slider, value, argument))
            return item

        self.add_head("General", expandable=True, expanded=True)
        # No "None" item needed as per plan, explicit none state is empty selection
        
        add_toggle_item("Master", "Master")
        add_toggle_item("Microphone", "Microphone")
        add_toggle_item("System sounds", "System sounds")
        add_toggle_item("Focused application", "Focused application")
        add_toggle_item("Unbound", "Unbound")
        
        self.add_head("Active sounds", expandable=True, expanded=True)
        # Dynamic active sounds
        if self.audio_manager:
            try:
                 active_apps = self.audio_manager.get_all_audio_apps()
                 # active_apps might be a list of strings or dicts, depending on WindowsAudioDriver
                 # Based on AudioManager.get_all_audio_apps() -> returns driver.get_all_audio_apps()
                 # Typically returns a list of names.
                 
                 found_any = False
                 for app_name in active_apps:
                     if app_name in ["Master", "System Sounds", "Microphone"]:
                         continue # Already in General
                     add_toggle_item(app_name, app_name)
                     found_any = True
                     
                 if not found_any:
                     self.add_item("No active apps found", level=0)
            except Exception as e:
                print(f"Error fetching active apps: {e}")
                self.add_item("Error fetching apps", level=0)
        else:
             self.add_item("Audio Service Unavailable", level=0)
        
        # Static placeholders removed/replaced by dynamic logic
        # add_toggle_item("Chrome", "Chrome")
        # add_toggle_item("Spotify", "Spotify")
        # add_toggle_item("Discord", "Discord")
        
        self.add_head("Other applications", expandable=True, expanded=True)
        
        # Load and display saved custom apps
        saved_apps = settings_manager.get_app_list()
        if saved_apps:
            
            def create_delete_handler(app_name):
                 def on_right_click(pos):
                     # Use content_layout's parent widget as parent for menu
                     parent_widget = self.content_layout.parentWidget()
                     menu = QMenu(parent_widget) 
                     delete_action = QAction(f"Delete '{app_name}'", menu)
                     delete_action.triggered.connect(lambda: delete_app(app_name))
                     menu.addAction(delete_action)
                     
                     # Simple styling for the context menu to match dark theme
                     menu.setStyleSheet(f"""
                        QMenu {{
                            background-color: #1E1E1E;
                            color: #FFFFFF;
                            border: 1px solid #333333;
                        }}
                        QMenu::item {{
                            padding: 5px 20px;
                        }}
                        QMenu::item:selected {{
                            background-color: #333333;
                        }}
                     """)
                     
                     menu.exec(pos)
                 return on_right_click

            def delete_app(app_name):
                settings_manager.remove_app_from_list(app_name)
                # Refresh menu
                self.build_slider_menu(target_slider)
            
            for app_name in saved_apps:
                # Add check if it's already added to avoid dupes if logic fails, but loop is clean
                if not target_slider.has_variable(app_name): # Optional check?
                    pass
                add_toggle_item(app_name, app_name, extra_margin=20, on_right_click=create_delete_handler(app_name))
        
        # Input for new application
        def on_new_app_text(text):
            if text and text.strip():
                clean_text = text.strip()
                settings_manager.add_app_to_list(clean_text)
                # Refresh menu to show new item
                self.build_slider_menu(target_slider)
                
        def on_browse_click():
            file_dialog = QFileDialog()
            file_name, _ = file_dialog.getOpenFileName(None, "Select Application", "", "Executables (*.exe);;Shortcuts (*.lnk);;All Files (*)")
            
            if file_name:
                app_name = ""
                # Check extension
                _, ext = os.path.splitext(file_name)
                if ext.lower() == '.lnk':
                    # Resolve shortcut
                    if win32com:
                        try:
                            shell = win32com.client.Dispatch("WScript.Shell")
                            shortcut = shell.CreateShortCut(file_name)
                            target_path = shortcut.Targetpath
                            # Get exe name from target path
                            img_name = os.path.basename(target_path)
                            app_name = img_name
                        except Exception as e:
                            print(f"Error resolving shortcut: {e}")
                            # Fallback to shortcut filename
                            app_name = os.path.basename(file_name)
                    else:
                        # Fallback
                        app_name = os.path.basename(file_name)
                elif ext.lower() == '.exe':
                    app_name = os.path.basename(file_name)
                else:
                    # Generic fallback
                    app_name = os.path.basename(file_name)
                
                if app_name:
                    # Clean/Capitalize? 
                    # User request: "save that name in a list... variables... listed in the menu"
                    settings_manager.add_app_to_list(app_name)
                    # Refresh
                    self.build_slider_menu(target_slider)

        
        input_item = self.add_input_item("Select new application", initial_value="", level=0, show_icon=True, icon_name="search.svg", icon_callback=on_browse_click)
        input_item.value_changed.connect(on_new_app_text)

    def _handle_slider_toggle(self, item, slider, value, argument):
        # Check if we are trying to ENABLE the variable (it's currently not active)
        if not slider.has_variable(value, argument):
            # Verify if it's available elsewhere
            if hasattr(self, 'variable_validator') and self.variable_validator:
                conflicting_slider = self.variable_validator(value, argument, slider)
                if conflicting_slider:
                    # Validator returned a slider -> Conflict!
                    
                    # 1. Flash error on the Menu Item (Red)
                    if hasattr(item, 'flash_error'):
                        item.flash_error()
                        
                    # 2. Flash success (Green) on the Conflicting Slider (indicating ownership)
                    if hasattr(conflicting_slider, 'flash_success'):
                        conflicting_slider.flash_success()
                        
                    # Do not proceed
                    return

        slider.toggle_variable(value, argument)
        item.set_selected(slider.has_variable(value, argument))

    def build_button_menu(self, target_button):
        """Build the button configuration menu content."""
        self.clear()
        
        def add_action_item(name, value, argument=None, level=0, is_default=False):
            # Check if this action is the active one
            current_var = target_button.get_variable()
            is_selected = False
            if current_var:
                if current_var['value'] == value and current_var['argument'] == argument:
                    is_selected = True
            elif value == "None":
                 is_selected = True

            item = self.add_item(name, level=level, selected=is_selected, is_default=is_default)
            item.clicked.connect(lambda: self._handle_button_select(item, target_button, value, argument))
            return item

        self.add_head("General", expandable=True, expanded=True)
        
        # Explicit None option removed as per request
        # add_action_item("None", "None") 
        
        add_action_item("Play/Pause", "Play/Pause")
        add_action_item("Previous", "Previous")
        add_action_item("Next", "Next")
        add_action_item("Volume Up", "Volume Up")
        add_action_item("Volume Down", "Volume Down")
        add_action_item("Seek Backward", "Seek Backward")
        add_action_item("Seek Forward", "Seek Forward")

        self.add_head("Actions", expandable=True, expanded=True)
        
        # Mute with expandable sub-options
        mute_item = self.add_item("Mute", is_expandable=True)
        # Children
        add_action_item("Master", "Mute", "Master", level=1, is_default=True)
        add_action_item("Microphone", "Mute", "Microphone", level=1)
        add_action_item("System Sounds", "Mute", "System Sounds", level=1)
        add_action_item("Current Application", "Mute", "Current Application", level=1)
        
        # Add dynamic active audio apps (same as slider menu "Active sounds")
        if self.audio_manager:
            try:
                active_apps = self.audio_manager.get_all_audio_apps()
                for app_name in active_apps:
                    # Skip system/special apps already listed
                    if app_name not in ["Master", "System Sounds", "Microphone"]:
                        add_action_item(app_name, "Mute", app_name, level=1)
            except Exception as e:
                print(f"Error getting active audio apps: {e}")
        
        # Also add saved custom applications
        saved_apps = settings_manager.get_app_list()
        if saved_apps:
            for app_name in sorted(saved_apps):
                # Skip system/special apps and apps already added from active list
                if app_name not in ["Master", "Microphone", "System Sounds", "Current Application"]:
                    # Check if not already added from active apps
                    add_action_item(app_name, "Mute", app_name, level=1)
        
        # Switch Audio Output
        switch_item = self.add_item("Switch Audio Output", is_expandable=True)
        add_action_item("Cycle Through", "Switch Audio Output", "Cycle Through", level=1, is_default=True)
        add_action_item("Speakers", "Switch Audio Output", "Speakers", level=1)
        add_action_item("Headphones", "Switch Audio Output", "Headphones", level=1)
        
        # Keybind with input
        keybind_item = self.add_item("Keybind", is_expandable=True)
        
        # Determine initial value
        current_kb = ""
        current_var = target_button.get_variable()
        if current_var and current_var['value'] == "Keybind":
            current_kb = current_var.get('argument', "")
            keybind_item.set_selected(True)
            
        input_item = self.add_input_item("Write Keybind", initial_value=current_kb, level=1)
        
        # If keybind is already selected, set input item as active initially
        if keybind_item.is_selected():
            keybind_item.set_has_active_child(True)
            input_item.set_active(True)

        def update_ui_for_keybind(active: bool):
            # 1. Deselect others and reset active states
            for item in self.menu_items:
                item.set_selected(False)
                if hasattr(item, 'set_has_active_child'):
                    item.set_has_active_child(False)
            
            if active:
                keybind_item.set_selected(True)
                keybind_item.set_has_active_child(True)
                input_item.set_active(True)
            else:
                 # If deactivated, ensure keybind is off. 
                 # Loop above already did 'set_selected(False)' for all, including keybind and input.
                 pass

        def on_keybind_save(value):
            # Always enable/update when typing
            target_button.set_variable("Keybind", value)
            update_ui_for_keybind(True)
            
        def on_keybind_toggle():
            # Toggle logic triggered by parent click (via default child mechanism)
            current_var = target_button.get_variable()
            is_active = False
            if current_var and current_var['value'] == "Keybind":
                is_active = True
                
            if is_active:
                # Deactivate
                target_button.set_variable("None")
                update_ui_for_keybind(False)
            else:
                # Activate with current text value
                val = input_item.get_value()
                target_button.set_variable("Keybind", val)
                update_ui_for_keybind(True)
            
        input_item.value_changed.connect(on_keybind_save)
        input_item.clicked.connect(on_keybind_toggle) # Connected to parent click via default child logic
        
        # Launch App with browse
        launch_item = self.add_item("Launch app", is_expandable=True)
        
        current_app = ""
        current_path = "" # Argument 2
        launch_var = target_button.get_variable()
        launch_active = False
        if launch_var and launch_var['value'] == "Launch app":
            current_app = launch_var.get('argument', "")
            current_path = launch_var.get('argument2', "") # Get stored path
            launch_active = True
            
        browse_item = self.add_browse_item(initial_value=current_app, level=1)
        # Manually set the path if we have it
        if current_path:
            browse_item.current_path = current_path
        
        if launch_active:
            launch_item.set_selected(True)
            launch_item.set_has_active_child(True)
            browse_item.set_active(True)
            
        def update_ui_for_launch(active: bool):
            # 1. Deselect others and reset active states
            for item in self.menu_items:
                item.set_selected(False)
                if hasattr(item, 'set_has_active_child'):
                    item.set_has_active_child(False)
            
            if active:
                launch_item.set_selected(True)
                launch_item.set_has_active_child(True)
                browse_item.set_active(True)
        
        def on_app_selected(app_name, app_path):
            target_button.set_variable("Launch app", app_name, app_path)
            update_ui_for_launch(True)
            
        def on_browse_toggle():
             # Toggle logic triggered by parent click
            current_var = target_button.get_variable()
            is_active = False
            if current_var and current_var['value'] == "Launch app":
                is_active = True
                
            if is_active:
                # Deactivate
                target_button.set_variable("None")
                update_ui_for_launch(False)
            else:
                # Activate ONLY if we have a value?
                # "item will only activate once it was selected an app"
                # But if we toggle back ON, do we restore previous? 
                # BrowseItem.current_text holds the "previous" or default.
                # If current_text is "Browse an app" (default), we probably shouldn't activate?
                # Or we activate but variable is empty?
                # User said: "clicking... will call... save that text... item will only activate once it was selected an app"
                # If I click parent "Launch app" and no app is selected yet, it should probably expand but not set variable?
                # OR if I have an app selected previously (in memory of BrowseItem), I restore it.
                
                current_val = browse_item.current_text
                # Try to retrieve full path if known? 
                # BrowseItem stores 'current_text', but not the path explicitly in public var, 
                # but we can assume if text matches what we have, we might have the path or just restore from button variable if it matches?
                # Actually, if we are toggling ON, we usually want to restore what was previously on the button IF it was Launch App.
                # But we just checked `current_var` and it was NOT Launch App (is_active=False).
                
                # If we toggle ON, and BrowseItem has a value (e.g. from previous browse), we use it.
                # But we don't have the path stored in BrowseItem publicly except via internal state or if we pass it.
                # The user requirement: "restore... save that text... argument 2 used later"
                
                # If BrowseItem just selected something, it emitted signal and we saved it (and activated).
                # If we deactivated (None) and click parent again to Activate:
                # We want to restore previous "Launch app" state? But we lost it when we set to None.
                # Unless we keep it in memory or BrowseItem kept it.
                
                # BrowseItem keeps `current_text`. It doesn't keep `current_path` explicitly in my implementation yet.
                # I should probably update BrowseItem to store `current_path` too if I want to robustly restore it.
                # But for now, let's assume if we click parent and BrowseItem text is valid, we try to set it.
                # If path is missing, maybe just use text as path (simple apps) or empty?
                # User constraint: "store... location... as argument 2".
                
                # Let's rely on what BrowseItem just emitted? No, checking BrowseItem state.
                # If I want to support this toggle restoration fully, I should store `latest_path` in this scope or BrowseItem.
                
                # For now, simplistic approach: If text is not default, we try to set it.
                if current_val != browse_item.default_text:
                     # We don't have the path here if we only read `current_text`.
                     # I will update BrowseItem to has `current_path` to be safe, or just pass None for now?
                     # If I pass None, argument 2 is lost.
                     # Let's Assume BrowseItem has `current_path`. I should add it.
                     path = getattr(browse_item, 'current_path', None)
                     target_button.set_variable("Launch app", current_val, path)
                     update_ui_for_launch(True)
                else:
                    # Just expand? 
                    # Parent click behavior (toggle_expanded) is handled by MenuItem internal logic usually, 
                    # but here we overloded 'clicked' via 'activate_default_child'.
                    # If we don't activate, we should at least ensure it expands?
                    # The `activate_default_child` emits `clicked` on child.
                    # We are in that handler. 
                    # If we don't set variable, we effectively do nothing but maybe the expand animation happened?
                    # `MenuItem` handles expansion on arrow click. Body click triggers this.
                    # If body click does nothing (because no app), it feels broken.
                    # Maybe strictly open browse dialog if no app?
                    # For now, if no app, we just ensure it's expanded?
                    # But we can't easily force expand from here without ref access to parent easily (we have it though).
                    
                    # Implementation choice: If no app selected, treat parent click as "Try to browse" or just "Expand".
                    # If I assume user wants to browse, I could call browse?
                    # But user said "clicking on the search icon will call..."
                    
                    # Safest: If we have an app, toggle it. If not, do nothing (or remain inactive).
                    pass

        browse_item.app_selected.connect(on_app_selected)
        browse_item.clicked.connect(on_browse_toggle)

    def _handle_button_select(self, item, button, value, argument):
        # Check if we are interacting with the already active item
        current_var = button.get_variable()
        is_already_active = False
        if current_var:
            if current_var['value'] == value and current_var['argument'] == argument:
                is_already_active = True
        
        # Toggle Logic
        if is_already_active:
            # Deselect -> Set to None
            button.set_variable("None")
            new_selected_item = None # Nothing selected
        else:
            # Select new
            button.set_variable(value, argument)
            new_selected_item = item
        
        # Visual Update
        # 1. Deselect everything first
        for existing_item in self.menu_items:
            # Force update false even if it was false, to ensure clean state
            if existing_item.is_selected():
                existing_item.set_selected(False)
            
            # Reset parent active indicators
            if hasattr(existing_item, 'set_has_active_child'):
                existing_item.set_has_active_child(False)
        
        # 2. Select the new item if any
        if new_selected_item:
            new_selected_item.set_selected(True)
            
            # 3. Update parent if exists
            parent = self.parent_map.get(new_selected_item)
            if parent:
                parent.set_has_active_child(True)
                
        # Force layout update? usually not needed if widgets repaint


    
    def toggle_section(self, section_name: str):
        """Toggle visibility of items in a section with animation."""
        if section_name not in self.sections:
            return
            
        section = self.sections[section_name]
        container = section['container']
        
        # Header has already toggled its state via mousePressEvent
        is_expanded = section['header'].is_expanded()
        section['expanded'] = is_expanded
        
        # Animation
        if not section.get('anim'):
            section['anim'] = QPropertyAnimation(container, b"maximumHeight")
            section['anim'].setDuration(200)
            section['anim'].setEasingCurve(QEasingCurve.InOutQuad)
            # Connect finish handler once or disconnect before connecting
            
        anim = section['anim']
        anim.stop()
        
        # Disconnect any previous finished connections to avoid stacking
        try:
            anim.finished.disconnect()
        except:
            pass
        
        if is_expanded:
            container.show()
            # Animate from 0 to full height
            height = section['layout'].sizeHint().height()
            
            # If sizeHint is insufficient, calculate manually
            if height <= 20:  # 20 is just margins/spacing
                 count = section['layout'].count()
                 height = count * 50 + 20 # 40px item + 10px spacing
            
            start_h = 0
            end_h = height
            
            anim.setStartValue(start_h)
            anim.setEndValue(end_h)
        else:
            # Animate from current height to 0
            anim.setStartValue(container.height())
            anim.setEndValue(0)
            anim.finished.connect(lambda: container.hide())
            
        anim.start()

    def toggle_item_expand(self, item, expanded):
        """Toggle sub-menu container visibility with animation."""
        if item not in self.item_containers:
            return
            
        data = self.item_containers[item]
        container = data['container']
        
        # Animation
        if not data['anim']:
            data['anim'] = QPropertyAnimation(container, b"maximumHeight")
            data['anim'].setDuration(200)
            data['anim'].setEasingCurve(QEasingCurve.InOutQuad)
        
        anim = data['anim']
        anim.stop()
        
        # Disconnect cleanup
        try:
            anim.finished.disconnect()
        except:
            pass
            
        if expanded:
            container.show()
            # Calculate height
            height = data['layout'].sizeHint().height()
            if height <= 20:
                 count = data['layout'].count()
                 height = count * 50 + 10
            
            anim.setStartValue(0)
            anim.setEndValue(height)
        else:
            anim.setStartValue(container.height())
            anim.setEndValue(0)
            anim.finished.connect(lambda: container.hide())
            
        anim.start()
    
    def activate_default_child(self, parent_item):
        """Activate the default child of a parent item."""
        if parent_item in self.default_children:
            child = self.default_children[parent_item]
            # Use emit to trigger whatever handler is attached (slider/button specific or generic)
            child.clicked.emit()
        else:
            # Fallback: Toggle expansion if no default child
            if hasattr(parent_item, 'toggle_expanded'):
                parent_item.toggle_expanded()
    
    def handle_item_clicked(self, clicked_item: MenuItem):
        """Handle menu item selection logic."""
        clicked_level = clicked_item.level
        
        # --- LEVEL 1 ITEMS (Child Items) ---
        if clicked_level == 1:
            # Must have a parent to work correctly in this system
            parent = self.parent_map.get(clicked_item)
            if not parent:
                return # Should not happen if built correctly
                
            # If the item is already selected, DESELECT it (Toggle behavior)
            if clicked_item.is_selected():
                clicked_item.set_selected(False)
                # Parent no longer has an active child (unless multi-select, but we assume single)
                parent.set_has_active_child(False)
                return

            # If item is NOT selected, SELECT it
            # 1. Deselect all other siblings
            if parent in self.item_containers:
                siblings = self.item_containers[parent]['items']
                for sibling in siblings:
                    if sibling != clicked_item and isinstance(sibling, MenuItem):
                        sibling.set_selected(False)
            
            # 2. Select the clicked item
            clicked_item.set_selected(True)
            
            # 3. Update Parent State (Has active child)
            # Ensure we strictly set this property
            parent.set_has_active_child(True)
            
            # 4. Clear 'active child' state from ALL other expandable parents
            # ensuring mutual exclusivity of "Active Section" if desired
            for other_parent in self.item_containers:
                if other_parent != parent:
                    # Force False to ensure UI updates
                    other_parent.set_has_active_child(False)
                    # Also deselect children of other parents to enforce single-selection global menu behavior
                    for child in self.item_containers[other_parent]['items']:
                        if isinstance(child, MenuItem):
                            child.set_selected(False)
                            
        # --- LEVEL 0 ITEMS (Independent/Parent Items) ---
        else:
            # If it's a simple toggle item (like "Master" or "Mute" if they were level 0)
            # Just toggle selection
            clicked_item.set_selected(not clicked_item.is_selected())
            
            # If this Level 0 item is also a Parent (Expandable), 
            # we might want to ensure its children are reset or handled?
            # But usually Level 0 expandable click = Default Action -> handled by activate_default_child
            pass
        # REMOVED recursive emit: clicked_item.clicked.emit()
