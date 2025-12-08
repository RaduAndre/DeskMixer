"""
Main window for DeskMixer UI.
Frameless window with custom title bar, volume sliders, action buttons, and sliding menu.
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QScrollArea, QGridLayout,
                               QSystemTrayIcon, QMenu)
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRect, QSize
from PySide6.QtGui import QIcon

from ui2.components.volume_slider import VolumeSlider
from ui2.components.action_button import ActionButton
from ui2.menu_builder import MenuBuilder
from ui2.icon_manager import icon_manager
from ui2.layout_calculator import calculate_button_layout
from ui2.settings_manager import settings_manager
from ui2 import colors, fonts


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1000, 600)
        self.setMinimumSize(800, 500)
        
        # State
        self._drag_pos = None
        self.selected_slider = None
        self.selected_button = None
        self.menu_open = False
        
        # Configuration
        self.slider_count = 4 
        self.button_count = 6
        
        self.setup_ui()
        self.setup_tray_icon()
    
    def setup_ui(self):
        """Setup the main UI."""
        # Central widget with background
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.BACKGROUND};
                border: 0px solid {colors.BORDER};
                border-radius: 0px;
            }}
        """)
        
        # Main layout (vertical: header + body)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # No padding
        self.main_layout.setSpacing(0)
        
        # Header
        self.setup_header()
        
        # Body (content + menu)
        self.setup_body()
    
    def setup_header(self):
        """Setup the header with window controls and app info."""
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        
        # Row 1: Window controls (minimize/close) - no margin from top
        controls_bar = QWidget()
        controls_layout = QHBoxLayout(controls_bar)
        controls_layout.setContentsMargins(0, 0, 15, 0)  # No top margin
        controls_layout.addStretch()
        
        self.btn_minimize = self.create_icon_button("minimise.svg", 12)
        self.btn_minimize.clicked.connect(self.hide)
        
        self.btn_close = self.create_icon_button("close.svg", 12)
        self.btn_close.clicked.connect(self.close)
        
        controls_layout.addWidget(self.btn_minimize)
        controls_layout.addSpacing(8)
        controls_layout.addWidget(self.btn_close)
        
        header_layout.addWidget(controls_bar)
        
        # Make header draggable
        header.mousePressEvent = self.header_mouse_press
        header.mouseMoveEvent = self.header_mouse_move
        
        self.main_layout.addWidget(header)
    
    def setup_body(self):
        """Setup the body with content area and menu."""
        body = QWidget()
        self.body_layout = QHBoxLayout(body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        
        # Content area
        self.content_area = QWidget()
        # Enable mouse tracking/events for content area to catch background clicks
        self.content_area.installEventFilter(self)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)
        
        # Controllers area (sliders + buttons) - removed settings button from here
        self.setup_controllers()
        self.content_layout.addWidget(self.controllers_area, 1)
        
        # Add a transparent blocker widget for click-outside-to-close
        self.menu_blocker = QWidget(self.content_area)
        self.menu_blocker.setStyleSheet("background-color: transparent;")
        self.menu_blocker.hide()
        self.menu_blocker.mousePressEvent = self.close_menu_on_click
        
        self.body_layout.addWidget(self.content_area, 1)
        
        # Menu area (initially hidden)
        self.setup_menu()
        self.body_layout.addWidget(self.menu_area)
        
        self.main_layout.addWidget(body, 1)
    
    def setup_controllers(self):
        """Setup the controllers area with sliders and buttons."""
        self.controllers_area = QWidget()
        self.controllers_area.installEventFilter(self) # Catch clicks
        main_layout = QVBoxLayout(self.controllers_area)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(10)
        
        # App info container (title + status + settings)
        info_container = QWidget()
        info_container.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.BACKGROUND};
                border: 0px solid {colors.BORDER};
                border-radius: 5px;
                padding: 2px 10px;
            }}
        """)
        info_container_layout = QHBoxLayout(info_container)
        info_container_layout.setContentsMargins(10, 2, 10, 2)
        info_container_layout.setSpacing(0)
        
        # Title and status (left side)
        title_status_widget = QWidget()
        title_status_layout = QVBoxLayout(title_status_widget)
        title_status_layout.setContentsMargins(0, 0, 0, 0)
        title_status_layout.setSpacing(2)
        
        title = QLabel("DeskMixer")
        title.setStyleSheet(f"""
            QLabel {{
                color: {colors.WHITE};
                font-size: 20px;
                font-family: Montserrat, Segoe UI;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
        
        self.status_label = QLabel("Connected")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.STATUS_CONNECTED};
                font-size: 15px;
                font-family: Montserrat, Segoe UI;
                background: transparent;
                border: none;
            }}
        """)
        
        title_status_layout.addWidget(title)
        title_status_layout.addWidget(self.status_label)
        
        info_container_layout.addWidget(title_status_widget)
        info_container_layout.addStretch()
        
        # Settings button (right side)
        self.btn_settings = self.create_icon_button("settings.svg", 20)
        self.btn_settings.clicked.connect(lambda: self.open_menu("settings"))
        info_container_layout.addWidget(self.btn_settings)
        
        main_layout.addWidget(info_container)
        
        # Sliders and buttons container (centered horizontally)
        controls_container = QWidget()
        layout = QHBoxLayout(controls_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # No gap between sliders and buttons
        layout.setAlignment(Qt.AlignHCenter)  # Center horizontally
        
        # Sliders container
        sliders_widget = QWidget()
        self.sliders_layout = QHBoxLayout(sliders_widget) # Save layout ref
        self.sliders_layout.setSpacing(2)
        self.sliders_layout.setContentsMargins(0, 0, 0, 0)
        self.sliders_layout.setAlignment(Qt.AlignLeft)
        
        # Restore Slider Order?
        # Get saved order
        saved_slider_order = settings_manager.get_slider_order() # ["slider_0", "slider_3", ...]
        
        default_names = ["Master", "Chrome", "Spotify", "System"]
        
        # Create sliders map/pool
        slider_pool = {} # ID -> Slider
        
        # Create all specific sliders first (pool)
        for i in range(self.slider_count):
            if i < len(default_names):
                name = default_names[i]
            else:
                name = f"Slider {i + 1}"
            
            # Stable ID
            s_id = f"slider_{i}"
            slider = VolumeSlider(name, index=0) # Index updated later
            slider.id = s_id
            slider.clicked.connect(lambda n=i, s=slider: self.on_slider_clicked(n, s))
            slider.dropped.connect(self.on_slider_dropped)
            
            slider_pool[s_id] = slider

        # Reconstruct self.sliders list based on saved order
        self.sliders = []
        
        # 1. Add saved ones
        if saved_slider_order:
            for s_id in saved_slider_order:
                if s_id in slider_pool:
                    self.sliders.append(slider_pool[s_id])
                    del slider_pool[s_id] # Mark as used
        
        # 2. Add remaining (new or unsaved)
        # Sort remaining by original ID index to keep stable default order?
        remaining = sorted(slider_pool.values(), key=lambda s: int(s.id.split('_')[1]))
        self.sliders.extend(remaining)
        
        # 3. Add to layout and update indices
        for i, slider in enumerate(self.sliders):
            slider.index = i # Update current index
            self.sliders_layout.addWidget(slider)

        layout.addWidget(sliders_widget)  # No stretch factor
        
        # Buttons container
        buttons_widget = QWidget()
        self.buttons_layout = QGridLayout(buttons_widget)
        self.buttons_layout.setSpacing(2)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Button Reordering/Restoration Logic
        # Similar logic. We use button_matrix flattened? 
        # User said "button order should be saved in a matrix variable".
        # If we just flatten the matrix, we get the order.
        saved_matrix = settings_manager.get_button_matrix()
        saved_button_order = []
        if saved_matrix:
            for row in saved_matrix:
                for b_id in row:
                    # We store "empty" in matrix.
                    saved_button_order.append(b_id) # Accept "empty" here
                        
        button_pool = {}
        
        button_pool = {}
        
        default_buttons = [
            ("play_pause.svg", "Play/Pause"),
            ("previous.svg", "Previous"),
            ("next.svg", "Next"),
            ("mute.svg", "Mute"),
            ("switch_output.svg", "Switch Output"),
            ("open_app.svg", "Open App")
        ]
        
        for i in range(self.button_count):
            if i < len(default_buttons):
                icon, text = default_buttons[i]
            else:
                icon, text = ("ghost.svg", "None")
                
            b_id = f"btn_{i}"
            button = ActionButton(icon, text, index=0) # index updated later
            button.id = b_id
            button.clicked.connect(lambda num=i, btn=button: self.on_button_clicked(num, btn))
            button.dropped.connect(self.on_button_dropped)
            
            button_pool[b_id] = button
            
        self.buttons = []
        
        if saved_button_order:
            for b_id in saved_button_order:
                if b_id == "empty":
                     # Create placeholder
                     # IMPORTANT: Pass parent
                     placeholder = ActionButton("ghost.svg", "None", index=0, parent=self.content_area)
                     placeholder.is_placeholder = True
                     placeholder.id = f"placeholder_{len(self.buttons)}" # Temp ID
                     placeholder.dropped.connect(self.on_button_dropped)
                     self.buttons.append(placeholder)
                elif b_id in button_pool:
                     self.buttons.append(button_pool[b_id])
                     del button_pool[b_id]
                     
        remaining_btns = sorted(button_pool.values(), key=lambda b: int(b.id.split('_')[1]))
        if remaining_btns:
            # Append remaining real buttons (flow into empty slots logic handled by grid resize if needed)
            # If matrix was smaller than current real buttons, we just append them.
            self.buttons.extend(remaining_btns)
        
        # Indices will be updated in update_button_grid
        for i, btn in enumerate(self.buttons):
            btn.index = i
            
        # Initial Layout
        self.update_button_grid(settings_manager.get_grid_dimensions())  # Pass tuple (rows, cols)
        
        layout.addWidget(buttons_widget)
        
        main_layout.addWidget(controls_container)
        
    def toggle_reorder_buttons(self, enabled: bool):
        """Toggle reorder mode for buttons."""
        self.reorder_buttons_mode = enabled
        for btn in self.buttons:
            btn.set_reorder_mode(enabled)
            
        if enabled:
            self.close_menu()
            # Also ensure visual update in case grid logic needs to show placeholders?
            # For now, just mode toggle.
            
    def toggle_reorder_sliders(self, enabled: bool):
        """Toggle reorder mode for sliders."""
        self.reorder_sliders_mode = enabled
        for slider in self.sliders:
            slider.set_reorder_mode(enabled)
            
        if enabled:
            self.reorder_buttons_mode = False # Exclusive
            self.close_menu()
            
    def on_button_dropped(self, source_idx, target_idx):
        """Handle button drop (swap)."""
        # source_idx is index in self.buttons list
        # target_idx is... wait. If target is a placeholder, it might be in the list?
        # Yes, we will put placeholders in self.buttons list so indices align with grid cells.
        
        if source_idx < 0 or source_idx >= len(self.buttons):
            return
        if target_idx < 0 or target_idx >= len(self.buttons):
            return

        b1 = self.buttons[source_idx]
        b2 = self.buttons[target_idx]
        
        # Swap in list
        self.buttons[source_idx], self.buttons[target_idx] = self.buttons[target_idx], self.buttons[source_idx]
        
        # Update indices
        self.buttons[source_idx].index = source_idx
        self.buttons[target_idx].index = target_idx
        
        # Update Visuals
        self.update_button_grid()
        
        # Save
        self.save_layout_settings()

    def on_slider_dropped(self, source_idx, target_idx):
        """Handle slider drop (swap)."""
        # Swap in list
        self.sliders[source_idx], self.sliders[target_idx] = self.sliders[target_idx], self.sliders[source_idx]
        
        # Update indices
        self.sliders[source_idx].index = source_idx
        self.sliders[target_idx].index = target_idx
        
        # Update Visuals
        self.update_slider_layout()
        
        # Save Order
        self.save_layout_settings()
        
    def  update_slider_layout(self):
        """Re-render sliders in correct order."""
        # Get layout from widget or... we have reference?
        # self.sliders is the list.
        # We need to access the layout. It's inside setup_controllers -> sliders_widget
        # I should save sliders_layout as self attribute.
        
        if not hasattr(self, 'sliders_layout'):
            return 
            
        # Clear layout
        while self.sliders_layout.count():
            item = self.sliders_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None) # Remove visual
                # We hide it then re-add, but here order matters fundamentally.
                # Since we want to reorder, removing and re-adding is best.
                # But we must ensure widget isn't destroyed. setParent(None) removes from hierarchy.
                # We hold ref in self.sliders.
        
        # Re-add in new order
        for s in self.sliders:
            # Ensure visible?
            # s.show() handled by logic
            self.sliders_layout.addWidget(s)

    def save_layout_settings(self):
        """Save current layout (button matrix and slider order)."""
        # Save Slider Order (List of IDs)
        # We need stable IDs. Let's use `slider.id` which we set at creation.
        slider_ids = [s.id for s in self.sliders]
        settings_manager.set_slider_order(slider_ids)
        
        # Save Button Matrix
        # Based on current Grid Size
        rows, cols = settings_manager.get_grid_dimensions()
        
        # If auto-calc was used (rows=0), we should probably calculate actual used dimensions?
        # But if user set Custom, we adhere to it.
        # If still 0, we fallback to logic.
        if rows == 0 or cols == 0:
             # Logic from update_button_grid
             import math
             n = len([b for b in self.buttons if b.get_variable() is not None]) # Count real buttons?
             # Actually self.buttons now contains placeholders.
             # We should count non-placeholders.
             real_btns = [b for b in self.buttons if not getattr(b, 'is_placeholder', False)]
             n = len(real_btns)
             if n > 0:
                cols = math.ceil(math.sqrt(n))
                rows = math.ceil(n / cols)
             else:
                rows, cols = 1, 1
        
        matrix = []
        count = 0
        for r in range(rows):
            row_list = []
            for c in range(cols):
                if count < len(self.buttons):
                    btn = self.buttons[count]
                    # Check if placeholder
                    if getattr(btn, 'is_placeholder', False):
                        row_list.append("empty")
                    else:
                        row_list.append(btn.id)
                    count += 1
                else:
                    row_list.append("empty") # or None
            matrix.append(row_list)
            
        settings_manager.set_button_matrix(matrix)


    def update_button_grid(self, dimensions: tuple[int, int] = None):
        """Update button grid layout based on grid settings, supporting sparse grid."""
        if dimensions:
            rows, cols = dimensions
        else:
             rows, cols = settings_manager.get_grid_dimensions()

        # Clear current items
        while self.buttons_layout.count():
            item = self.buttons_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Auto-calculate if 0
        # If 0, we imply "compact/auto" mode, so no placeholders usually.
        # But let's standardize.
        import math
        real_buttons = [b for b in self.buttons if not getattr(b, 'is_placeholder', False)]
        
        if rows == 0 or cols == 0:
            n = len(real_buttons)
            if n > 0:
                cols = math.ceil(math.sqrt(n))
                rows = math.ceil(n / cols)
            else:
                rows, cols = 1, 1
        
        # Ensure self.buttons matches total slots (rows * cols)
        # We need to fill self.buttons with placeholders if it's too short,
        # or remove placeholders if too long.
        total_slots = rows * cols
        
        # Rebuild self.buttons list to match grid size
        # We keep the "real" buttons in their relative order (linear read)?
        # Or we respect the current list order?
        # Issue: Changing grid size reshuffles everything.
        # If we expand, we append placeholders.
        # If we shrink, we wrap? Or drop? (Shouldn't drop real buttons).
        
        # Current list might contain placeholders from previous grid.
        # Filter placeholders out first to get "content".
        content_buttons = [b for b in self.buttons if not getattr(b, 'is_placeholder', False)]
        
        # But wait, if we are just re-rendering (e.g. after swap), we don't want to destroy layout.
        # We should only resize list if Grid Size Changed.
        # How to detect? We compare len(self.buttons) with total_slots.
        # If len == total -> Just render.
        # If len != total -> Resizing happened.
        
        if len(self.buttons) != total_slots:
            # Resizing logic
            new_list = []
            # Fill with existing content (skipping old placeholders usually? 
            # Or if we want to preserve "empty slot at index 1"? 
            # If resizing 3x3 -> 4x4, we append.
            # If resizing 3x3 -> 2x2, we might lose positions.
            # Best effort: Flatten current grid, take first N items that fit?
            # Or just reflow "Real" buttons into new grid?
            # Creating a "fresh start" for layout when resizing is acceptable.
            # Reflow real buttons sequentially.
            
            # Use 'real_buttons' (content)
            for i in range(total_slots):
                if i < len(real_buttons):
                    new_list.append(real_buttons[i])
                else:
                    # Create placeholder
                    # Placeholder is an ActionButton with special state?
                    # Or just "None" state but we mark it.
                    # IMPORTANT: Pass parent to avoid top-level window flash
                    placeholder = ActionButton("ghost.svg", "None", index=i, parent=self.content_area)
                    placeholder.is_placeholder = True
                    # Set ID to differentiate
                    placeholder.id = f"placeholder_{i}" 
                    placeholder.dropped.connect(self.on_button_dropped)
                    # Initialize in "None" state
                    placeholder.set_variable("None") 
                    new_list.append(placeholder)
            
            self.buttons = new_list
        
        # Render
        count = 0
        for r in range(rows):
            for c in range(cols):
                if count < len(self.buttons):
                    btn = self.buttons[count]
                    btn.index = count # Ensure index is synced
                    btn.show()
                    
                    # If reorder mode active, ensure placeholder has correct style/state?
                    if getattr(self, 'reorder_buttons_mode', False):
                        btn.set_reorder_mode(True)
                    else:
                        btn.set_reorder_mode(False) # Ensure off
                        
                    self.buttons_layout.addWidget(btn, r, c)
                    count += 1
            
        # Update widget size constraint
        container = self.buttons_layout.parentWidget()
        if container:
            container.setMaximumWidth(cols * 85 + (cols - 1) * 2)
    
    def setup_menu(self):
        """Setup the sliding menu."""
        self.menu_area = QWidget()
        self.menu_area.setFixedWidth(0)  # Initially hidden
        self.menu_area.setStyleSheet(f"""
            QWidget {{
                background-color: {colors.BLACK};
                border-left: 0px solid {colors.BORDER};
                border-radius: 0px;
            }}
        """)
        
        menu_layout = QVBoxLayout(self.menu_area)
        menu_layout.setContentsMargins(0, 0, 0, 0)
        menu_layout.setSpacing(0)
        
        # Menu header (fixed)
        menu_header = QWidget()
        menu_header.setFixedHeight(60)
        menu_header.setStyleSheet(f"background-color: {colors.BACKGROUND};")
        menu_header_layout = QHBoxLayout(menu_header)
        menu_header_layout.setContentsMargins(20, 15, 20, 15)
        
        self.menu_title = QLabel("Settings")
        self.menu_title.setStyleSheet(f"""
            QLabel {{
                {fonts.menu_name_style()}
                background: transparent;
            }}
        """)
        menu_header_layout.addWidget(self.menu_title)
        
        menu_layout.addWidget(menu_header)
        
        # Menu content (scrollable)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555;
                border-radius: 4px;
            }
        """)
        
        menu_content_widget = QWidget()
        menu_content_widget.setStyleSheet(f"background-color: {colors.BLACK};")
        self.menu_content_layout = QVBoxLayout(menu_content_widget)
        self.menu_content_layout.setContentsMargins(0, 20, 0, 20)
        self.menu_content_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(menu_content_widget)
        menu_layout.addWidget(scroll_area)
        
        # Menu builder
        self.menu_builder = MenuBuilder(self.menu_content_layout)
        # self.menu_builder.on_alignment_changed = self.update_button_grid # Deprecated
        self.menu_builder.on_grid_changed = lambda r, c: self.update_button_grid((r, c))
        self.menu_builder.variable_validator = self.check_variable_availability

        # Grid Validator: Ensure grid is large enough for current buttons
        def check_grid_size(r, c):
             total_slots = r * c
             # Count real buttons (exclude placeholders)
             real_button_count = len([b for b in self.buttons if not getattr(b, 'is_placeholder', False)])
             if total_slots < real_button_count:
                 # Too small
                 return False
             return True
             
        self.menu_builder.grid_validator = check_grid_size

        self.menu_builder.on_reorder_buttons_toggled = self.toggle_reorder_buttons
        self.menu_builder.on_reorder_sliders_toggled = self.toggle_reorder_sliders
        
        # Connect reorder toggles from menu
        self.menu_builder.on_reorder_buttons_toggled = self.toggle_reorder_buttons
        self.menu_builder.on_reorder_sliders_toggled = self.toggle_reorder_sliders
        
    def check_variable_availability(self, value: str, argument: str, exclude_slider: VolumeSlider):
        """
        Check if a variable is available (not bound to other sliders).
        Returns None if available, or the conflicting VolumeSlider object if taken.
        """
        for slider in self.sliders:
            if slider == exclude_slider:
                continue
            if slider.has_variable(value, argument):
                return slider
        return None

    
    def create_icon_button(self, icon_name: str, size: int) -> QPushButton:
        """Create a simple icon button."""
        btn = QPushButton()
        icon = icon_manager.get_icon(icon_name)
        btn.setIcon(icon)
        btn.setIconSize(QSize(size, size))
        btn.setFixedSize(size + 10, size + 10)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
            }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        return btn
    
    def update_settings_icon(self, active: bool):
        """Update settings button icon based on active state."""
        # Settings Icon: White (default) / Accent (active)
        target_color = colors.ACCENT if active else colors.WHITE
        icon = icon_manager.get_colored_icon("settings.svg", target_color)
        self.btn_settings.setIcon(icon)
        self.btn_settings.setIconSize(QSize(20, 20))
    
    def on_slider_clicked(self, slider_num: int, slider: VolumeSlider):
        """Handle slider click."""
        # Deselect previous slider
        if self.selected_slider and self.selected_slider != slider:
            self.selected_slider.set_active(False)
        
        # Select this slider
        self.selected_slider = slider
        slider.set_active(True)
        
        # Open menu
        self.open_menu("slider", slider_num)
    
    def on_button_clicked(self, button_num: int, button: ActionButton):
        """Handle button click."""
        # Note: Buttons handle their own toggle state
        # Just open the menu
        self.selected_button = button
        self.open_menu("button", button_num)
    
    def open_menu(self, menu_type: str, item_num: int = 0):
        """Open the sliding menu."""
        # Update menu title and build menu content
        if menu_type == "settings":
            self.menu_title.setText("Settings")
            self.menu_builder.build_settings_menu()
            # Set settings icon to active
            self.update_settings_icon(True)
            # Deactivate slider/button when opening settings  
            if self.selected_slider:
                self.selected_slider.set_active(False)
                self.selected_slider = None
            if self.selected_button:
                self.selected_button.set_active(False)
                self.selected_button = None
        elif menu_type == "slider":
            self.menu_title.setText(f"Slider {item_num + 1}")
            self.menu_builder.build_slider_menu(self.selected_slider)
            # Restore normal settings icon
            self.update_settings_icon(False)
            # Deactivate button when opening slider menu
            if self.selected_button:
                self.selected_button.set_active(False)
                self.selected_button = None
        elif menu_type == "button":
            self.menu_title.setText(f"Button {item_num + 1}")
            self.menu_builder.build_button_menu(self.selected_button)
            # Restore normal settings icon
            self.update_settings_icon(False)
            # Deactivate slider when opening button menu
            if self.selected_slider:
                self.selected_slider.set_active(False)
                self.selected_slider = None
        
        # Connect menu item clicks to selection handler - REMOVED
        # Menu items now have specific handlers attached by MenuBuilder during build
        # for item in self.menu_builder.menu_items:
        #     item.clicked.connect(lambda i=item: self.menu_builder.handle_item_clicked(i))
        
        # Animate menu opening if not already open
        if not self.menu_open:
            # Show blocker to catch clicks outside menu
            self.menu_blocker.setGeometry(self.content_area.rect())
            self.menu_blocker.raise_()
            self.menu_blocker.show()
            
            self.animate_menu(300)
            self.menu_open = True
    
    def animate_menu(self, target_width: int):
        """Animate the menu sliding."""
        # Animate menu width
        self.menu_anim = QPropertyAnimation(self.menu_area, b"minimumWidth")
        self.menu_anim.setDuration(300)
        self.menu_anim.setStartValue(self.menu_area.width())
        self.menu_anim.setEndValue(target_width)
        self.menu_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Also animate maximum width to ensure it changes
        self.menu_anim2 = QPropertyAnimation(self.menu_area, b"maximumWidth")
        self.menu_anim2.setDuration(300)
        self.menu_anim2.setStartValue(self.menu_area.width())
        self.menu_anim2.setEndValue(target_width)
        self.menu_anim2.setEasingCurve(QEasingCurve.InOutQuad)
        
        # Animate controllers area to shrink/expand when menu opens/closes
        current_content_width = self.content_area.width()
        if target_width > 0:
            # Menu opening - leave space for menu
            target_content_width = current_content_width - target_width
        else:
            # Menu closing - use full width
            target_content_width = self.body_layout.geometry().width()
        
        self.content_anim = QPropertyAnimation(self.content_area, b"maximumWidth")
        self.content_anim.setDuration(300)
        self.content_anim.setStartValue(current_content_width)
        self.content_anim.setEndValue(target_content_width)
        self.content_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        self.menu_anim.start()
        self.menu_anim2.start()
        self.content_anim.start()
        
        
        # Hide blocker when closing
        if target_width == 0:
            self.menu_anim.finished.connect(self.menu_blocker.hide)
    
    def close_menu(self):
        """Close the menu."""
        if self.menu_open:
            # Deactivate any selected slider or button when menu closes
            if self.selected_slider:
                self.selected_slider.set_active(False)
                self.selected_slider = None
            if self.selected_button:
                self.selected_button.set_active(False)
                self.selected_button = None
            
            # Restore normal settings icon
            self.update_settings_icon(False)
            
            self.animate_menu(0)
            self.menu_open = False
    
    def close_menu_on_click(self, event):
        """Close menu when clicking outside of it (not on sliders/buttons)."""
        # This is called when clicking on the blocker widget
        # Clicking sliders/buttons will trigger their own menu opening logic
        self.close_menu()
        event.accept()
    
    def header_mouse_press(self, event):
        """Handle header mouse press for window dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def header_mouse_move(self, event):
        """Handle header mouse move for window dragging."""
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def set_status(self, status: str):
        """Set the connection status."""
        status_colors = {
            "Connected": colors.STATUS_CONNECTED,
            "Trying to connect": colors.STATUS_TRYING,
            "Disconnected": colors.STATUS_DISCONNECTED
        }
        
        self.status_label.setText(status)
        color = status_colors.get(status, colors.STATUS_CONNECTED)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 10px;
                font-family: Montserrat, Segoe UI;
                background: transparent;
            }}
        """)
    
    def setup_tray_icon(self):
        """Setup the system tray icon."""
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Set icon - try to use the app icon, or a default one
        try:
            icon = icon_manager.get_icon("logo.ico")  # Placeholder, replace with app icon if available
            self.tray_icon.setIcon(icon)
        except:
            # Fallback to a default icon
            self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        # Set tooltip
        self.tray_icon.setToolTip("DeskMixer")
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Restore action
        restore_action = tray_menu.addAction("Restore")
        restore_action.triggered.connect(self.show_from_tray)
        
        # Quit action
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)
        
        # Set menu to tray icon
        self.tray_icon.setContextMenu(tray_menu)
        
        # Double-click to restore
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Show the tray icon
        self.tray_icon.show()
    
    def on_tray_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_from_tray()
    
    def show_from_tray(self):
        """Restore the window from tray."""
        self.show()
        self.activateWindow()
        self.raise_()



    def eventFilter(self, obj, event):
        """Event filter to handle background clicks for cancelling reorder mode."""
        from PySide6.QtCore import QEvent, QObject
        if (obj == self.content_area or obj == getattr(self, 'controllers_area', None)) and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                # Helper to check if a widget is child of another (or is the widget itself)
                def is_descendant(child, parent_type):
                    current = child
                    while current:
                        if isinstance(current, parent_type):
                            return True
                        current = current.parent()
                    return False
                
                # Get the widget under the mouse cursor
                clicked_widget = QApplication.widgetAt(event.globalPosition().toPoint())
                
                # Check Reorder Buttons
                if getattr(self, 'reorder_buttons_mode', False):
                    # Check if clicked widget is part of any ActionButton
                    if is_descendant(clicked_widget, ActionButton):
                        return False # Don't handle, let button handle it
                        
                    self.toggle_reorder_buttons(False)
                    return True # Handled
                     
                # Check Reorder Sliders
                if getattr(self, 'reorder_sliders_mode', False):
                    # Check if clicked widget is part of any VolumeSlider
                    if is_descendant(clicked_widget, VolumeSlider):
                        return False # Don't handle, let slider handle it
                        
                    self.toggle_reorder_sliders(False)
                    return True
                     
        return super().eventFilter(obj, event)

def main():
    """Run the application."""
    # Fix for window resize glitch on moving between screens
    # Force System DPI Awareness (1) instead of Per-Monitor (2)
    # This prevents the window from trying to resize itself when crossing screens with different DPIs,
    # which causes the "expansion glitch" in frameless windows.
    # We must set this before creating the generic QApplication.
    os.environ["QT_QPA_PLATFORM"] = "windows:dpiawareness=1"

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
