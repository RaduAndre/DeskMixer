"""
Overlay widget displayed on top of the button grid.
Represents a device screen display.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, Signal
from ui2 import colors, fonts


class ScreenOverlay(QWidget):
    """Screen overlay widget positioned at the top-center of the button grid.
    Represents the device screen."""
    
    clicked = Signal() # Signal emitted when clicked
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Enable styled background for QWidget stylesheets to work
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI components."""
        # Set fixed size with 2:1 aspect ratio (similar to button size 70x70, but wider)
        # Using 140x70 for 2:1 ratio
        self.setFixedSize(140, 70)
        
        # Enable mouse tracking for hover effect
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor) # Indicate clickable
        
        # Apply initial style
        self.update_style()
        
        # Add a label inside for device screen display
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignCenter)
        
        self.screen_label = QLabel("Screen")
        self.screen_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.WHITE};
                font-size: 14px;
                font-family: Montserrat, Segoe UI;
                background: transparent;
                border: none;
            }}
        """)
        self.screen_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.screen_label)
    
    def update_style(self):
        """Update stylesheet with current theme colors."""
        self.setStyleSheet(f"""
            ScreenOverlay {{
                background-color: {colors.BLACK};
                border: 1px solid {colors.BORDER};
                border-radius: 10px;
                padding: 5px;
            }}
            ScreenOverlay:hover {{
                background-color: #1a1a1a;
                border: 1px solid {colors.ACCENT};
            }}
        """)
    
    def refresh_theme(self):
        """Refresh theme when accent color changes."""
        self.update_style()
        # Update label color if needed
        self.screen_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.WHITE};
                font-size: 14px;
                font-family: Montserrat, Segoe UI;
                background: transparent;
                border: none;
            }}
        """)
        self.update()
    
    def set_visible_state(self, active: bool):
        """Set visibility based on screen_active from Arduino configuration.
        
        Args:
            active (bool): True to show screen, False to hide
        """
        self.setVisible(active)

    def mousePressEvent(self, event):
        """Handle mouse click"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)



