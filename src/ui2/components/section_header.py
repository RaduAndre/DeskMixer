"""
Custom section header widget for menu sections.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QTransform
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts


class SectionHeader(QWidget):
    """Section header with optional expandable icon."""
    
    clicked = Signal()
    
    def __init__(self, text: str, expandable: bool = False, expanded: bool = True, parent=None):
        super().__init__(parent)
        self.text = text
        self.expandable = expandable
        self._expanded = expanded
        self._rotation = -90 if expanded else 0  # -90 = Expanded (CCW), 0 = Collapsed
        
        self.setStyleSheet("background: transparent;")
        if expandable:
            self.setCursor(Qt.PointingHandCursor)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(10)
        
        # Header text
        self.label = QLabel(self.text)
        self.label.setStyleSheet(f"""
            QLabel {{
                {fonts.menu_name_style()}
                background: transparent;
            }}
        """)
        layout.addWidget(self.label)
        
        if self.expandable:
            # Add stretch to push icon to the right
            layout.addStretch()
            
            # Expand/collapse icon
            self.icon_label = QLabel()
            self.icon_label.setFixedSize(20, 20)
            self.icon_label.setStyleSheet("background: transparent;")
            self.update_icon_rotation()
            layout.addWidget(self.icon_label)
            
            # Setup rotation animation
            self.anim = QPropertyAnimation(self, b"rotation")
            self.anim.setDuration(200)
            self.anim.setEasingCurve(QEasingCurve.InOutQuad)
    
    def get_rotation(self):
        return self._rotation
        
    def set_rotation(self, angle):
        self._rotation = angle
        self.update_icon_rotation()
        
    rotation = Property(float, get_rotation, set_rotation)
    
    def update_icon_rotation(self):
        """Update the icon with current rotation."""
        if not self.expandable:
            return
            
        icon = icon_manager.get_icon("expand.svg")
        pixmap = icon.pixmap(20, 20)
        
        transform = QTransform()
        transform.rotate(self._rotation)
        
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self.icon_label.setPixmap(rotated_pixmap)
    
    def toggle_expanded(self):
        """Toggle expanded state with animation."""
        if self.expandable:
            self.set_expanded(not self._expanded)
    
    def is_expanded(self) -> bool:
        """Get expanded state."""
        return self._expanded
    
    def set_expanded(self, expanded: bool):
        """Set expanded state with animation."""
        self._expanded = expanded
        
        if self.expandable:
            start_val = self._rotation
            end_val = -90 if expanded else 0
            
            self.anim.stop()
            self.anim.setStartValue(start_val)
            self.anim.setEndValue(end_val)
            self.anim.start()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks."""
        if event.button() == Qt.LeftButton and self.expandable:
            self.toggle_expanded()
            self.clicked.emit()
        super().mousePressEvent(event)
