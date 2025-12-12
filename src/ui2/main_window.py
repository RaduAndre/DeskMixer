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
from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRect, QSize, Signal
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
    
    # Signal for thread-safe status updates
    status_update_signal = Signal(str, str)
    # Signal for thread-safe volume updates from backend
    volume_update_signal = Signal(str, int)
    # Signal for thread-safe button press notifications
    button_press_signal = Signal(str)
    
    def __init__(self, audio_manager=None, version="Unknown"):
        super().__init__()
        self.audio_manager = audio_manager
        self.version = version  # Store version for settings menu
        
        # Window setup
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1000, 600)
        self.setMinimumSize(800, 500)
        self.setWindowTitle("DeskMixer") # Critical for FindWindow
        
        # Enable performance optimizations
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        
        # Set window icon for taskbar
        try:
            icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'icons', 'logo.ico'))
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Failed to load window icon: {e}")
        
        # State
        self._drag_pos = None
        self.selected_slider = None
        self.selected_button = None
        self.menu_open = False
        
        # Configuration
        self.slider_count = 4 
        self.button_count = 6
        
        # Connect signals
        self.status_update_signal.connect(self.on_status_update)
        self.volume_update_signal.connect(self.update_slider_by_target)
        self.button_press_signal.connect(self.on_button_press_from_device)
        
        self.setup_ui()
        self.setup_tray_icon()
        
        # Sync initial slider positions with current volumes
        self.sync_initial_volumes()
        
        
    def on_button_press_from_device(self, device_button_id: str):
        """Handle button press from device (e.g., 'b5' from device -> 'btn_4' in UI)."""
        # Device buttons are 1-indexed (b1, b2, ...), UI buttons are 0-indexed (btn_0, btn_1, ...)
        # Extract number from device_button_id (e.g., "b5" -> 5)
        try:
            if device_button_id.startswith('b'):
                device_num = int(device_button_id[1:])
                # Convert to UI ID (subtract 1)
                ui_num = device_num - 1
                ui_button_id = f"btn_{ui_num}"
                # Trigger highlight
                self.highlight_button_by_id(ui_button_id)
        except (ValueError, IndexError) as e:
            from utils.error_handler import log_error
            log_error(e, f"Error parsing device button ID: {device_button_id}")
        
    def on_status_update(self, status: str, message: str):
        """Handle status update from background thread."""
        # Map SerialHandler status to UI status
        status_map = {
            "connected": ("Connected", colors.STATUS_CONNECTED), # Green
            "connecting": ("Trying to connect", "#FFA500"),      # Orange/Yellow
            "reconnecting": ("Trying to connect", "#FFA500"),    # Orange/Yellow
            "disconnected": ("Disconnected", colors.STATUS_DISCONNECTED) # Red
        }
        
        ui_status, color = status_map.get(status.lower(), ("Disconnected", colors.STATUS_DISCONNECTED))
        
        # User requested verifying specific text changes only, not style
        # But subsequently clarified "make the ui change the style of the status so if its disconnected red trying to connect or reconnecting yellow and connected green"
        
        # Apply Text
        self.status_label.setText(ui_status)
        
        # Apply Color (Update stylesheet for color only, preserving other font settings)
        current_style = self.status_label.styleSheet()
        # We need to construct a new style with the correct color
        # Since we use a function in setup_ui but modified it previously?
        # Let's just set the specific style properties we know.
        
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-size: 15px;
                font-family: Montserrat, Segoe UI;
                background: transparent;
                border: none;
            }}
        """)
    
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
        # User requested explicitly initiating program closing
        self.btn_close.clicked.connect(QApplication.quit)
        
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
    
    # ... (previous code)
    
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
        
        self.status_label = QLabel("Disconnected") # Default to disconnected
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.STATUS_DISCONNECTED};
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
        
        # Initialize Sliders from Config
        self.sliders = []
        slider_order = settings_manager.get_slider_order()
        
        # If no order, but we have variable bindings, imply order from them? 
        # Or if order is empty, check how many sX keys exist.
        if not slider_order:
            # Check for s1, s2... keys
            count = 0
            while True:
                key = f"s{count + 1}"
                if settings_manager.config_manager.load_variable_binding(key):
                    count += 1
                else:
                     # Stop if gap? Or just assume 4 default.
                     if count == 0: count = 4
                     break
            
            # Generate default order
            slider_order = [f"slider_{i}" for i in range(count)]
            settings_manager.set_slider_order(slider_order)
            
        # Create sliders based on order
        for i, s_id in enumerate(slider_order):
            # Parse index from ID for stable naming (Slider 1, etc.)
            try:
                idx = int(s_id.split('_')[1])
                name = f"Slider {idx + 1}"
            except:
                name = "Slider"
                
            slider = VolumeSlider(name, index=len(self.sliders))
            slider.id = s_id
            
            # Restore Bindings by LOGICAL ID (e.g. slider_0 -> s1)
            # This ensures binding stays with the slider identity regardless of visual order.
            try:
                logical_idx = int(s_id.split('_')[1])
                bindings = settings_manager.get_slider_binding_at_index(logical_idx)
                if bindings:
                    slider.set_variables(bindings)
            except:
                pass
                
            slider.clicked.connect(lambda n=len(self.sliders), s=slider: self.on_slider_clicked(n, s))
            slider.dropped.connect(self.on_slider_dropped)
            
            # Connect change signal for auto-save
            slider.variableChanged.connect(self.save_bindings)
            
            self.sliders.append(slider)
            self.sliders_layout.addWidget(slider)

        layout.addWidget(sliders_widget)  # No stretch factor
        
        # Buttons container
        buttons_widget = QWidget()
        self.buttons_layout = QGridLayout(buttons_widget)
        self.buttons_layout.setSpacing(2)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # Initialize Buttons from Config
        self.buttons = []
        button_matrix = settings_manager.get_button_matrix()
        
        # Default if missing
        if not button_matrix:
            # Default 2x3 matrix
            count = 6
            cols = 3
            import math
            rows = math.ceil(count / cols)
            
            button_matrix = []
            c = 0
            for r in range(rows):
                row = []
                for col in range(cols):
                    if c < count:
                        row.append(f"btn_{c}")
                    else:
                        row.append("empty")
                    c += 1
                button_matrix.append(row)
            settings_manager.set_button_matrix(button_matrix)
            settings_manager.set_grid_dimensions(rows, cols)
            
        # Flatten matrix to create buttons list
        flat_order = []
        for row in button_matrix:
             for b_id in row:
                 flat_order.append(b_id)
                 
        for i, b_id in enumerate(flat_order):
            if b_id == "empty":
                 placeholder = ActionButton("ghost.svg", "None", index=i, parent=self.content_area)
                 placeholder.is_placeholder = True
                 placeholder.id = f"placeholder_{i}"
                 placeholder.dropped.connect(self.on_button_dropped)
                 self.buttons.append(placeholder)
            else:
                 # Real button
                 try:
                     idx = int(b_id.split('_')[1])
                 except:
                     idx = i
                 
                 btn = ActionButton("ghost.svg", "None", index=i) # Text updated by set_variable
                 btn.id = b_id
                 
                 # Restore Binding by LOGICAL ID
                 # This ensures binding stays with the button identity regardless of visual order.
                 try:
                     logical_idx = int(b_id.split('_')[1])
                     binding = settings_manager.get_button_binding_at_index(logical_idx)
                     if binding:
                         btn.set_variable(binding.get('value'), binding.get('argument'), binding.get('argument2'))
                 except:
                     pass
                 
                 btn.clicked.connect(lambda num=i, b=btn: self.on_button_clicked(num, b))
                 btn.dropped.connect(self.on_button_dropped)
                 
                 # Connect change signal
                 btn.variableChanged.connect(self.save_bindings)
                 
                 self.buttons.append(btn)
        
        # Update layout
        rows, cols = settings_manager.get_grid_dimensions()
        if rows == 0 or cols == 0:
             # Infer from matrix
             rows = len(button_matrix)
             cols = len(button_matrix[0]) if rows > 0 else 0
             settings_manager.set_grid_dimensions(rows, cols)
             
        # Call update_button_grid WITHOUT dimensions to avoid triggering the 
        # "Resize & Sort" logic. We want to preserve the matrix order we just loaded.
        self.update_button_grid()
        
        layout.addWidget(buttons_widget)
        
        main_layout.addWidget(controls_container)
        
        # Connect Hardware Signals from Singleton/Core
        # Assuming we can access CoreController instance or internal Audio/Serial
        # Since we instantiated CoreController in main.py, we really should pass it or access it.
        # But `CoreController` isn't a singleton itself (it's instantiated).
        # We need to bridge this. `main.py` created it. 
        # However, `main_window` was instantiated cleanly.
        # Fix: access it via global or import based on existing structure?
        # The prompt says "once the device is connected it will send the number of sliders".
        
    def update_device_layout(self, num_sliders: int, num_buttons: int):
        """Update layout based on hardware capabilities."""
        # Update Sliders
        current_sliders = len(self.sliders)
        
        if num_sliders > current_sliders:
            # Add new sliders
            start_idx = current_sliders
            for i in range(start_idx, num_sliders):
                s_id = f"slider_{i}" 
                # Ensure it doesn't duplicate logic if we re-use IDs or have gaps?
                # Just sequential for now.
                
                # Check if we recycled an old ID that has bindings?
                slider = VolumeSlider(f"Slider {i + 1}", index=len(self.sliders))
                slider.id = s_id
                
                # Try to restore binding if it existed previously for this ID
                try:
                    logical_idx = int(s_id.split('_')[1])
                    bindings = settings_manager.get_slider_binding_at_index(logical_idx)
                    if bindings:
                       slider.set_variables(bindings)
                except:
                    pass
                   
                slider.clicked.connect(lambda n=len(self.sliders), s=slider: self.on_slider_clicked(n, s))
                slider.dropped.connect(self.on_slider_dropped)
                slider.variableChanged.connect(self.save_bindings) # Connect signal
                
                self.sliders.append(slider)
                self.sliders_layout.addWidget(slider)
                
        elif num_sliders < current_sliders:
            # Remove last LOGICAL slider (highest ID), regardless of visual position
            diff = current_sliders - num_sliders
            for _ in range(diff):
                # Find slider with highest ID index
                max_id = -1
                target_slider = None
                
                for s in self.sliders:
                    try:
                        sid = int(s.id.split('_')[1])
                        if sid > max_id:
                            max_id = sid
                            target_slider = s
                    except:
                        pass
                
                if target_slider:
                    self.sliders.remove(target_slider)
                    target_slider.setParent(None)
                    target_slider.deleteLater()
                else:
                    # Fallback if IDs parsing fails
                    slider = self.sliders.pop()
                    slider.setParent(None)
                    slider.deleteLater()
        
        # Update Slider Order Config
        self.save_layout_settings()

    def update_slider_volume_by_id(self, slider_id: str, volume: int):
        """Update slider volume and trigger highlight animation.
        
        Args:
            slider_id (str): The logical ID of the slider (e.g., 'slider_0').
            volume (int): The new volume level (0-100).
        """
        for slider in self.sliders:
            if hasattr(slider, 'id') and slider.id == slider_id:
                # set_value handles animation and highlight if implemented in VolumeSlider
                slider.set_value(volume)
                break
                
    def update_slider_by_target(self, target_name: str, volume: int):
        """Update slider(s) bound to a specific target."""
        # Find which slider is bound to this target
        # We check active_variables of each slider
        
        # Normalize target name for case-insensitive comparison
        target_lower = target_name.lower() if target_name else ""
        
        for slider in self.sliders:
            if not hasattr(slider, 'active_variables'):
                continue
                
            for var in slider.active_variables:
                # check value (e.g. 'Master', 'chrome.exe') or argument
                val = var.get('value')
                arg = var.get('argument')
                
                # Normalize for comparison
                val_lower = val.lower() if val else ""
                arg_lower = arg.lower() if arg else ""
                
                # Match against either value or argument (some bindings might be complex)
                # Usually target_name is the app name or "Master"
                if val_lower == target_lower or arg_lower == target_lower:
                    self.update_slider_volume_by_id(slider.id, volume)
                    # Don't break, multiple sliders *could* theoretically be bound to same thing

    def sync_initial_volumes(self):
        """Query current volumes from audio system and update slider positions on startup."""
        if not self.audio_manager:
            return
            
        try:
            # Get audio driver
            driver = self.audio_manager.driver
            if not driver:
                return
            
            # Query volumes for each bound slider
            for slider in self.sliders:
                if not hasattr(slider, 'active_variables') or not slider.active_variables:
                    continue
                
                # Get first binding to determine target
                for var in slider.active_variables:
                    value = var.get('value')
                    if not value:
                        continue
                    
                    volume = None
                    
                    # Query volume based on binding type - access interfaces directly
                    if value == "Master":
                        if driver.master_volume:
                            try:
                                volume = driver.master_volume.GetMasterVolumeLevelScalar()
                            except Exception:
                                pass
                                
                    elif value == "Microphone":
                        if driver.mic_volume:
                            try:
                                volume = driver.mic_volume.GetMasterVolumeLevelScalar()
                            except Exception:
                                pass
                                
                    elif value == "System Sounds" or value == "System sounds":
                        # System sounds has multiple sessions
                        if hasattr(driver, 'system_sounds_sessions') and driver.system_sounds_sessions:
                            try:
                                volume = driver.system_sounds_sessions[0].GetSimpleAudioVolume(None).GetMasterVolume()
                            except Exception:
                                pass
                                
                    else:
                        # Application-specific volume
                        if hasattr(driver, 'app_sessions') and value in driver.app_sessions:
                            try:
                                sessions = driver.app_sessions[value]
                                if sessions:
                                    volume = sessions[0].GetSimpleAudioVolume(None).GetMasterVolume()
                            except Exception:
                                pass
                    
                    # Update slider if volume was retrieved
                    if volume is not None:
                        self.update_slider_volume_by_id(slider.id, int(volume * 100))
                        break  # Only use first binding for initial sync
                        
        except Exception as e:
            print(f"Error syncing initial volumes: {e}")


    def highlight_button_by_id(self, button_id: str):
        """Highlight a button by its logical ID.
        
        Args:
            button_id (str): The logical ID of the button (e.g., 'btn_0').
        """
        for btn in self.buttons:
            if getattr(btn, 'is_placeholder', False):
                continue
                
            if hasattr(btn, 'id') and btn.id == button_id:
                if hasattr(btn, 'highlight'):
                    btn.highlight()
                break

    def update_device_layout(self, num_sliders: int, num_buttons: int):
        """Update layout based on hardware capabilities."""
        # Update Sliders
        current_sliders = len(self.sliders)
        
        if num_sliders > current_sliders:
            # Add new sliders
            start_idx = current_sliders
            for i in range(start_idx, num_sliders):
                s_id = f"slider_{i}" 
                
                slider = VolumeSlider(f"Slider {i + 1}", index=len(self.sliders))
                slider.id = s_id
                
                # Try to restore binding if it existed previously for this ID
                try:
                    logical_idx = int(s_id.split('_')[1])
                    bindings = settings_manager.get_slider_binding_at_index(logical_idx)
                    if bindings:
                       slider.set_variables(bindings)
                except:
                    pass
                   
                slider.clicked.connect(lambda n=len(self.sliders), s=slider: self.on_slider_clicked(n, s))
                slider.dropped.connect(self.on_slider_dropped)
                slider.variableChanged.connect(self.save_bindings)
                
                self.sliders.append(slider)
                self.sliders_layout.addWidget(slider)
                
        elif num_sliders < current_sliders:
            # Remove last LOGICAL slider (highest ID), regardless of visual position
            diff = current_sliders - num_sliders
            for _ in range(diff):
                # Find slider with highest ID index
                max_id = -1
                target_slider = None
                
                for s in self.sliders:
                    try:
                        sid = int(s.id.split('_')[1])
                        if sid > max_id:
                            max_id = sid
                            target_slider = s
                    except:
                        pass
                
                if target_slider:
                    self.sliders.remove(target_slider)
                    target_slider.setParent(None)
                    target_slider.deleteLater()
                else:
                    # Fallback if IDs parsing fails
                    slider = self.sliders.pop()
                    slider.setParent(None)
                    slider.deleteLater()
        
        # Update Slider Order Config
        self.save_layout_settings()

        # Update Buttons
        # Count REAL buttons
        real_buttons = [b for b in self.buttons if not getattr(b, 'is_placeholder', False)]
        current_buttons = len(real_buttons)
        
        if num_buttons > current_buttons:
            # Add buttons
            start = current_buttons
            for i in range(start, num_buttons):
                b_id = f"btn_{i}"
                btn = ActionButton("ghost.svg", "None", index=0)
                btn.id = b_id
                
                btn.clicked.connect(lambda: None)
                self.buttons.append(btn)
        
        elif num_buttons < current_buttons:
            # Remove last real buttons by LOGICAL ID (highest ID)
            to_remove = current_buttons - num_buttons
            
            for _ in range(to_remove):
                max_id = -1
                target_btn = None
                
                for btn in self.buttons:
                    if getattr(btn, 'is_placeholder', False):
                        continue
                    
                    try:
                        bid = int(btn.id.split('_')[1])
                        if bid > max_id:
                            max_id = bid
                            target_btn = btn
                    except:
                        pass
                
                if target_btn:
                    self.buttons.remove(target_btn)
                    target_btn.setParent(None)
                    target_btn.deleteLater()
                else:
                    # Fallback
                    # Find last non-placeholder
                    for i in range(len(self.buttons) - 1, -1, -1):
                        btn = self.buttons[i]
                        if not getattr(btn, 'is_placeholder', False):
                            self.buttons.pop(i)
                            btn.setParent(None)
                            btn.deleteLater()
                            break
                        
        # Trigger grid recalculation
        self.update_button_grid()
        self.save_layout_settings()

    def toggle_reorder_buttons(self, enabled: bool):
        """Toggle reorder mode for buttons."""
        self.reorder_buttons_mode = enabled
        for btn in self.buttons:
            btn.set_reorder_mode(enabled)
            
        if enabled:
            self.close_menu()
            
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
        if source_idx < 0 or source_idx >= len(self.buttons):
            return
        if target_idx < 0 or target_idx >= len(self.buttons):
            return

        # Swap in list
        self.buttons[source_idx], self.buttons[target_idx] = self.buttons[target_idx], self.buttons[source_idx]
        
        # Update indices
        self.buttons[source_idx].index = source_idx
        self.buttons[target_idx].index = target_idx
        
        # Update Visuals
        self.update_button_grid()
        
        # Save Layout
        self.save_layout_settings()
        
        # Save Bindings (Order changed, so Positional Bindings must update)
        # e.g. b1 is now what b2 was.
        self.save_bindings()

    def on_slider_dropped(self, source_idx, target_idx):
        """Handle slider drop (swap)."""
        # Swap in list
        self.sliders[source_idx], self.sliders[target_idx] = self.sliders[target_idx], self.sliders[source_idx]
        
        # Update indices
        for i, s in enumerate(self.sliders):
             s.index = i
        
        # Update Visuals
        self.update_slider_layout()
        
        # Save Order
        self.save_layout_settings()
        
        # Save Bindings (Positional update)
        self.save_bindings()
        
    def save_bindings(self, *args):
        """Save all current bindings based on current positions."""
        # Save Sliders: Logical ID -> s(ID+1)
        for slider in self.sliders:
            try:
                logical_idx = int(slider.id.split('_')[1])
                settings_manager.save_slider_binding_at_index(logical_idx, slider.active_variables)
            except:
                pass
            
        # Save Buttons: Logical ID -> b(ID+1)
        for btn in self.buttons:
            if getattr(btn, 'is_placeholder', False):
                 pass
            else:
                 try:
                     logical_idx = int(btn.id.split('_')[1])
                     var = btn.get_variable()
                     settings_manager.save_button_binding_at_index(logical_idx, var)
                 except:
                     pass
                 
        # ConfigManager usually saves on add_binding immediately, 
        # but if we do bulk, we might want to optimize? 
        # Currently it auto-saves. That's fine for user interaction speed.
        
    def  update_slider_layout(self):
        """Re-render sliders in correct order."""
        if not hasattr(self, 'sliders_layout'):
            return 
            
        # Clear layout (remove from view but keep object)
        for _ in range(self.sliders_layout.count()):
             self.sliders_layout.takeAt(0)
        
        # Re-add in new order
        for s in self.sliders:
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
        if rows == 0 or cols == 0:
             import math
             n = len([b for b in self.buttons if not getattr(b, 'is_placeholder', False)])
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
        settings_manager.set_grid_dimensions(rows, cols)


    def update_button_grid(self, dimensions: tuple[int, int] = None):
        """Update button grid layout based on grid settings, supporting sparse grid."""
        if dimensions:
            rows, cols = dimensions
            settings_manager.set_grid_dimensions(rows, cols)
        else:
             rows, cols = settings_manager.get_grid_dimensions()

        # Clear current items
        while self.buttons_layout.count():
            item = self.buttons_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        
        # Rebuild self.buttons list if size changed significantly or we want to normalize placeholders?
        # For now, assumes self.buttons matches rows*cols logic roughly or we reflow.
        # Ensure list size matches content
        
        total_slots = rows * cols
        
        # Check if we need to rebuild the list
        # We rebuild if:
        # 1. Grid dimensions explicitly changed (dimensions arg provided)
        # 2. Total slots mismatch (e.g. initial load or resize)
        # 3. We want to force reflow (rare here)
        
        should_rebuild = False
        if dimensions is not None:
             should_rebuild = True
        elif len(self.buttons) != total_slots:
             should_rebuild = True
             
        if should_rebuild:
            # Filter placeholders out first to get "content"
            content_buttons = [b for b in self.buttons if not getattr(b, 'is_placeholder', False)]
            
            # SORT by Logical ID to restore default order "1 2 3 4" on grid resize
            def get_btn_id(b):
                try:
                    return int(b.id.split('_')[1])
                except:
                    return 0
            content_buttons.sort(key=get_btn_id)
            
            # Rebuild full list
            new_list = []
            
            for i in range(total_slots):
                 if i < len(content_buttons):
                     new_list.append(content_buttons[i])
                 else:
                     # Create placeholder
                     # Check if we can reuse existing placeholders? No, simpler to recreate or just use logic.
                     # Recreating is safer for IDs.
                     placeholder = ActionButton("ghost.svg", "None", index=i, parent=self.content_area)
                     placeholder.is_placeholder = True
                     placeholder.id = f"placeholder_{i}" 
                     placeholder.dropped.connect(self.on_button_dropped)
                     placeholder.set_variable("None") 
                     new_list.append(placeholder)
                     
            self.buttons = new_list
        else:
            # Just reusing existing list (sparse layout preserved)
            # Ensure indices are correct in the loop below
            pass

        # Render
        count = 0
        for r in range(rows):
            for c in range(cols):
                if count < len(self.buttons):
                    btn = self.buttons[count]
                    btn.index = count # Ensure index is synced
                    btn.show()
                    
                    if getattr(self, 'reorder_buttons_mode', False):
                        btn.set_reorder_mode(True)
                    else:
                        btn.set_reorder_mode(False)
                        
                    self.buttons_layout.addWidget(btn, r, c)
                    count += 1
            
        # Update widget size constraint
        container = self.buttons_layout.parentWidget()
        if container:
            container.setMaximumWidth(cols * 85 + (cols - 1) * 2)
            
        # If dimensions changed explicitly, save the new default layout immediately
        if dimensions:
             self.save_layout_settings()
    
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
        self.menu_builder = MenuBuilder(self.menu_content_layout, self.audio_manager)
        self.menu_builder.version = self.version  # Pass version for settings menu display
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
            title_num = item_num + 1
            if self.selected_slider and hasattr(self.selected_slider, 'id'):
                try:
                    title_num = int(self.selected_slider.id.split('_')[1]) + 1
                except:
                    pass
            self.menu_title.setText(f"Slider {title_num}")
            self.menu_builder.build_slider_menu(self.selected_slider)
            # Restore normal settings icon
            self.update_settings_icon(False)
            # Deactivate button when opening slider menu
            if self.selected_button:
                self.selected_button.set_active(False)
                self.selected_button = None
        elif menu_type == "button":
            title_num = item_num + 1
            if self.selected_button and hasattr(self.selected_button, 'id'):
                try:
                    title_num = int(self.selected_button.id.split('_')[1]) + 1
                except:
                    pass
            self.menu_title.setText(f"Button {title_num}")
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
        # Animate menu width (250ms for smooth feel)
        self.menu_anim = QPropertyAnimation(self.menu_area, b"minimumWidth")
        self.menu_anim.setDuration(250)  # Increased to 250ms for smoother animation
        self.menu_anim.setStartValue(self.menu_area.width())
        self.menu_anim.setEndValue(target_width)
        self.menu_anim.setEasingCurve(QEasingCurve.OutCubic)  # Changed to OutCubic for snappier feel
        
        # Also animate maximum width to ensure it changes
        self.menu_anim2 = QPropertyAnimation(self.menu_area, b"maximumWidth")
        self.menu_anim2.setDuration(250)  # Increased to 250ms
        self.menu_anim2.setStartValue(self.menu_area.width())
        self.menu_anim2.setEndValue(target_width)
        self.menu_anim2.setEasingCurve(QEasingCurve.OutCubic)  # Changed to OutCubic
        
        # Don't animate content_area - it causes slider repaints and lag
        # Let Qt handle the layout automatically
        # The HBoxLayout will naturally shrink content_area as menu_area grows
        
        self.menu_anim.start()
        self.menu_anim2.start()
        
        
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
        quit_action.triggered.connect(self.quit_application)
        
        # Set menu to tray icon
        self.tray_icon.setContextMenu(tray_menu)
        
        # Double-click to restore
        self.tray_icon.activated.connect(self.on_tray_activated)
        
        # Show the tray icon
        self.tray_icon.show()
    
    def quit_application(self):
        """Quit the application completely."""
        QApplication.quit()

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
