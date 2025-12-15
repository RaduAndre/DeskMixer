"""
Input menu item with text box and icon.
"""

import sys
import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts


class InputItem(QWidget):
    """Menu item with an input text box and an icon."""
    
    value_changed = Signal(str) # Signal emitted when value is saved (focus lost)
    clicked = Signal() # Signal for activation via parent

    
    def __init__(self, placeholder: str = "", initial_value: str = "", level: int = 0, show_icon: bool = True, icon_name: str = "record.svg", icon_callback=None, parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.current_value = initial_value
        self.level = level
        self._active = False # State to track active status
        
        self.show_icon = show_icon
        self.icon_name = icon_name
        self.icon_callback = icon_callback
        
        # Make the main widget transparent
        self.setStyleSheet("background: transparent;")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup UI components."""
        # Main layout with margins for spacing based on level
        main_layout = QHBoxLayout(self)
        
        # Calculate padding based on level (same logic as MenuItem)
        left_margin = 15 + (self.level * 15) + 20
        main_layout.setContentsMargins(left_margin, 0, 15, 0)
        main_layout.setSpacing(0)
        
        # Container box
        self.container = QWidget()
        self.container.setObjectName("container_box")
        self.container.setFixedHeight(50)
        
        # Style for the container (Input element style)
        self.update_style()
        
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(15, 0, 15, 0)
        container_layout.setSpacing(10)
        
        # Text Input
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(self.placeholder)
        self.input_field.setText(self.current_value)
        self.input_field.setFrame(False) # No default border
        
        # Input Style
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                color: {colors.WHITE};
                font-family: Montserrat, Segoe UI;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
                selection-background-color: {colors.ACCENT};
                selection-color: {colors.BLACK};
            }}
        """)
        
        container_layout.addWidget(self.input_field, 1)
        
        if self.show_icon:
            # Icon (Right side)
            self.icon_label = QLabel()
            self.icon_label.setFixedSize(20, 20)
            self.icon_label.setStyleSheet("background: transparent;")
            
            # Set icon
            icon = icon_manager.get_colored_icon(self.icon_name, colors.WHITE)
            self.icon_label.setPixmap(icon.pixmap(20, 20))
            
            # Make clickable if callback provided
            if self.icon_callback:
                self.icon_label.setCursor(Qt.PointingHandCursor)
                # Install event filter or subclass? 
                # Simpler: just overwrite mousePressEvent for this label instance or wrap it
                # Monkey patching instance method
                def mousePressEvent(event):
                    if event.button() == Qt.LeftButton:
                        self.icon_callback()
                self.icon_label.mousePressEvent = mousePressEvent
            
            container_layout.addWidget(self.icon_label)
        
        main_layout.addWidget(self.container)
        
        # Logic for saving value
        # We want to save when "im leaving the textbox with the cursor or gets out of focus"
        # editingFinished is emitted on Return/Enter press OR focus loss.
        self.input_field.editingFinished.connect(self._handle_editing_finished)
        
    def _handle_editing_finished(self):
        """Handle input completion."""
        new_value = self.input_field.text()
        # Only emit if valid? Or always?
        # User said "once im done writing it saves that value"
        # We can emit always.
        self.value_changed.emit(new_value)
        # Check if we should update current_value locally
        self.current_value = new_value

    def set_value(self, value):
        """Set the input value programmatically."""
        self.current_value = value
        self.input_field.setText(value)

    def get_value(self):
        """Get the current value."""
        return self.input_field.text()
    
    def set_active(self, active: bool):
        """Set active state (show border)."""
        self._active = active
        self.update_style()
        
    def set_selected(self, selected: bool):
        """Compat alias for set_active to work with MenuBuilder loops."""
        self.set_active(selected)
        
    def is_selected(self) -> bool:
        """Compat method for MenuBuilder loops."""
        return self._active
        
    def update_style(self):
        """Update container style based on state."""
        border_style = f"1px solid {colors.ACCENT}" if self._active else "0px solid transparent"
        
        # When active, we don't need hover effect to change border, or we keep it?
        # User said "stay active as long as its active".
        # If it's active, the border is already there. Hover can add to it or substitute?
        # If active, hover generally doesn't need to do much else.
        # But we must ensure the "active" border persists.
        
        # CSS logic:
        # If active -> border is accent.
        # If not active -> border is transparent, hover -> accent.
        
        self.container.setStyleSheet(f"""
            #container_box {{
                background-color: {colors.BLACK};
                border-radius: 13px;
                border: {border_style};
            }}
            #container_box:hover {{
                border: 1px solid {colors.ACCENT};
            }}
        """)

    def flash_error(self):
        """Flash the border red to indicate error."""
        from PySide6.QtCore import QTimer
        from ui2 import colors
        
        # We need to override the style temporarily
        # Current logic uses #container_box ID selector
        
        error_style = f"""
            #container_box {{
                background-color: {colors.BLACK};
                border-radius: 13px;
                border: 2px solid #FF4444;
            }}
        """
        
        self.container.setStyleSheet(error_style)
        
        # Revert after 500ms
        QTimer.singleShot(500, lambda: self.update_style())

    def refresh_theme(self):
        """Refresh theme colors."""
        # Update Input Style
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                color: {colors.WHITE};
                font-family: Montserrat, Segoe UI;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
                selection-background-color: {colors.ACCENT};
                selection-color: {colors.BLACK};
            }}
        """)
        
        # Update Icon
        if self.show_icon:
            # Re-get colored icon
            icon = icon_manager.get_colored_icon(self.icon_name, colors.WHITE)
            self.icon_label.setPixmap(icon.pixmap(20, 20))
            
        # Update Container Style
        self.update_style()
