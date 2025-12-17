"""
Menu builder for constructing menu content dynamically.
Coordinator for specialized menu components.
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
from ui2.icon_manager import icon_manager 
from utils import system_startup
from PySide6.QtWidgets import QFileDialog, QMenu
from PySide6.QtGui import QAction, QCursor

# Import separate menu components
from ui2.components.menu.settings_menu import SettingsMenu
from ui2.components.menu.slider_menu import SliderMenu
from ui2.components.menu.button_menu import ButtonMenu
from ui2.components.menu.screen_menu import ScreenMenu

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
        
        # State
        self.active_menu_type = None
        self.reorder_sliders_mode = False
        self.reorder_buttons_mode = False
        
        self.variable_validator = None # Callback(value, argument, exclude_obj) -> conflicting_obj
        self.grid_validator = None # Callback(rows, cols) -> bool
        
        # Initialize sub-components
        self.settings_menu = SettingsMenu(self)
        self.slider_menu = SliderMenu(self)
        self.button_menu = ButtonMenu(self)
        self.screen_menu = ScreenMenu(self)
    
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
        
        if level == 0:
            # Level 0 items go to section container if available
            if self.current_section and self.current_section in self.sections:
                target_layout = self.sections[self.current_section]['layout']
                self.sections[self.current_section]['items'].append(item)
        elif level == 1:
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
        
        if level == 0:
            # Level 0 items go to section container if available
            if self.current_section and self.current_section in self.sections:
                target_layout = self.sections[self.current_section]['layout']
                self.sections[self.current_section]['items'].append(item)
        elif level == 1:
            if self.current_parent_item and self.current_parent_item in self.item_containers:
                target_layout = self.item_containers[self.current_parent_item]['layout']
                self.item_containers[self.current_parent_item]['items'].append(item)
                
                # Register as default child
                self.default_children[self.current_parent_item] = item
        
        target_layout.addWidget(item)
        self.menu_items.append(item)
        return item
    
    
    # --- Delegated Menu Builders ---
    
    def build_settings_menu(self):
        """Build the settings menu content."""
        self.settings_menu.build_menu()

    def refresh_theme(self):
        """Update styles for all current menu items."""
        # Refresh section headers
        for section_name, data in self.sections.items():
            if 'header' in data and data['header']:
                data['header'].refresh_theme()
                
        # Refresh items
        for item in self.menu_items:
            if hasattr(item, 'refresh_theme'):
                item.refresh_theme()
    
    def build_slider_menu(self, target_slider):
        """Build the slider configuration menu content."""
        self.slider_menu.build_menu(target_slider)

    def build_button_menu(self, target_button):
        """Build the button configuration menu content."""
        self.button_menu.build_menu(target_button)

    def build_screen_menu(self):
        """Build the screen configuration menu content."""
        self.screen_menu.build_menu()
        
    # --- Helper Methods exposed for components (if needed, or kept here if shared) ---
    
    def _open_color_picker(self, item, all_items):
        """Open color picker dialog (Moved from original/shared helper)."""
        from ui2.components.color_picker import ColorPickerDialog
        
        # Get global position of the item for popup positioning
        # Approximate good position
        global_pos = item.mapToGlobal(item.rect().center())
        
        # Assuming we can get parent for modal
        parent = self.content_layout.parentWidget() 
        while parent and not parent.isWindow():
             parent = parent.parentWidget()
             
        initial = settings_manager.get_accent_color()
        if not initial: initial = "#00EAD0"
        
        dialog = ColorPickerDialog(initial_color=initial, parent=parent)
        # Center or position near menu? Center on screen is safer.
        
        if dialog.exec():
            new_color = dialog.selected_color
            if new_color:
                # Update settings
                settings_manager.set_accent_color(new_color)
                # Update Theme
                colors.set_accent(new_color)
                
                # Update UI Selection
                item.set_selected(True)
                # Deselect others
                for other in all_items:
                    if other != item:
                        other.set_selected(False)
                        
                # Update label of custom item if it exists, or create separate logic
                # For now just refreshing entire menu is easiest way to show new hex?
                # But we act "live".
                if hasattr(item, 'color_id'):
                    pass # It's a color item
                else:
                    # Rename "Select new color..." to HEX? 
                    # Re-building menu is cleaner to show state
                    self.build_settings_menu()

    def _set_accent(self, item, all_items):
        """Set accent color from preset."""
        color = getattr(item, 'color_id', None)
        if color:
             if color == "teal": color = "#00EAD0"
             
             settings_manager.set_accent_color(color)
             colors.set_accent(color)
             
             item.set_selected(True)
             for other in all_items:
                 if other != item:
                     other.set_selected(False)
                     
             # Rebuild to refresh custom hex display if needed
             self.build_settings_menu()

    # --- Section & Animation Handling (kept in MenuBuilder as it manages layout) ---
    
    def toggle_section(self, section_name):
        """Toggle section expansion."""
        if section_name not in self.sections:
            return
            
        data = self.sections[section_name]
        is_expanded = data['expanded']
        
        # Stop existing animation
        if data['anim']:
            data['anim'].stop()
            
        container = data['container']
        layout = data['layout']
        
        # Calculate target height based on content
        # Force layout update to get real size hint
        # Layouts can be tricky.
        # Simple approach: measure sum of heights?
        # Or let QWidget sizeHint work.
        
        if is_expanded:
            # Collapse
            start_h = container.height()
            end_h = 0
            data['header'].set_expanded(False)
            data['expanded'] = False
        else:
            # Expand
            container.show()
            # Measure content
            # Try setting fixed height big, then sizeHint, then restore?
            # Or just set limits unconstrained
            container.setMaximumHeight(10000) # Uncap
            container.adjustSize()
            target_h = container.sizeHint().height()
            
            start_h = 0
            end_h = target_h
            
            # Temporarily set back to 0 for animation start
            container.setMaximumHeight(0) 
            
            data['header'].set_expanded(True)
            data['expanded'] = True
            
        # Animate max height
        anim = QPropertyAnimation(container, b"maximumHeight")
        anim.setDuration(200)
        anim.setStartValue(start_h)
        anim.setEndValue(end_h)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        
        # Cleanup
        def on_finished():
            if not data['expanded']:
                container.hide()
            else:
                 # Remove limit so it can grow if content changes dynamically?
                 # Actually content changes often rebuild menu.
                 # Better to keep it adaptable.
                 container.setMaximumHeight(16777215) 
        
        anim.finished.connect(on_finished)
        anim.start()
        data['anim'] = anim
        
    def toggle_item_expand(self, item, expanded):
        """Toggle expandable item sub-container."""
        if item not in self.item_containers:
            return
            
        data = self.item_containers[item]
        container = data['container']
        
        if data['anim']:
            data['anim'].stop()
            
        if not expanded:
            # Collapse
            start_h = container.height()
            end_h = 0
            
            # Collapse parent section if needed? No.
        else:
             # Expand
             container.show()
             container.setMaximumHeight(10000)
             container.adjustSize()
             target_h = container.sizeHint().height()
             
             start_h = 0
             end_h = target_h
             container.setMaximumHeight(0)
             
        anim = QPropertyAnimation(container, b"maximumHeight")
        anim.setDuration(150)
        anim.setStartValue(start_h)
        anim.setEndValue(end_h)
        anim.setEasingCurve(QEasingCurve.OutQuad)
        
        def on_finished():
            if not expanded:
                container.hide()
            else:
                container.setMaximumHeight(16777215)
                
        anim.finished.connect(on_finished)
        anim.start()
        data['anim'] = anim
        
        # When expanding an item, update active state
        if expanded:
            # Close other items in same section? Not requested but standard accordio behavior optionally.
            # Here we allow multiple open.
            pass

    def activate_default_child(self, parent_item):
        """When clicking parent body, activate its default child."""
        if parent_item in self.default_children:
            child = self.default_children[parent_item]
            # Simulate click on child
            # But we must be careful not to create recursion if child click re-triggers parent logic.
            # Child click usually just sets variable.
            
            # Trigger click signal on child
            child.emit_clicked_signal() 
            # Note: We added emit_clicked_signal to MenuItem for this purpose if direct .click() fails or is protected.
            # Actually MenuItem inherits QWidget/QFrame. We can just call the slot if we know what it does.
            # But we connected lambdas to item.clicked.
            # So easiest is to emit the signal.
            
    # Handle dynamic grid/reorder signal callbacks
    def handle_item_clicked(self, item):
        # Generic handler if needed
        pass
