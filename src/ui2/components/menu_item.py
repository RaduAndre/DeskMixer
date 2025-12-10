"""
Custom menu item widget with radio-button style selection.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QColor, QPen, QTransform
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts


class RadioCircle(QWidget):
    """Radio button circle indicator."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected = False
        self.active_child = False
        self.setFixedSize(20, 20)
        self.setStyleSheet("background: transparent;")
    
    def set_selected(self, selected: bool):
        """Set selected state."""
        self.selected = selected
        self.repaint()
        
    def set_active_child(self, active: bool):
        """Set active child state."""
        self.active_child = active
        self.repaint()
    
    def paintEvent(self, event):
        """Paint the radio circles."""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Circle center
        circle_center_x = 10
        circle_center_y = 10
        
        if self.selected:
            # Active state: outer circle = black, inner circle = accent
            # Outer circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.BLACK))
            painter.drawEllipse(circle_center_x - 8, circle_center_y - 8, 16, 16)
            
            # Inner circle (accent color)
            painter.setBrush(QColor(colors.ACCENT))
            painter.drawEllipse(circle_center_x - 5, circle_center_y - 5, 10, 10)
        elif self.active_child:
            # Active child state: outer circle = background (inactive), inner circle = accent
            # Outer circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.BACKGROUND))
            painter.drawEllipse(circle_center_x - 8, circle_center_y - 8, 16, 16)
            
            # Inner circle (accent color)
            painter.setBrush(QColor(colors.ACCENT))
            painter.drawEllipse(circle_center_x - 5, circle_center_y - 5, 10, 10)
        else:
            # Inactive state: outer circle = background, inner circle = background
            # Outer circle
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(colors.BACKGROUND))
            painter.drawEllipse(circle_center_x - 8, circle_center_y - 8, 16, 16)
            
            # Inner circle (background color)
            painter.setBrush(QColor(colors.BACKGROUND))
            painter.drawEllipse(circle_center_x - 5, circle_center_y - 5, 10, 10)
        
        painter.end()



class MenuItem(QWidget):
    """Menu item with radio-button circles and text."""
    
    clicked = Signal()
    toggled = Signal(bool)  # Signal for expansion toggle
    
    def __init__(self, text: str, level: int = 0, selected: bool = False, 
                 is_expandable: bool = False, is_default: bool = False, extra_margin: int = 0, on_right_click=None, parent=None):
        super().__init__(parent)
        self.text = text
        self.level = level
        self._selected = selected
        self.is_expandable = is_expandable
        self.is_default = is_default
        self.extra_margin = extra_margin
        self.on_right_click = on_right_click
        self._expanded = False
        self._has_active_child = False
        self._rotation = -90 if self._expanded else 0  # -90 = Expanded (CCW), 0 = Collapsed
        
        # Make the main widget transparent - it only serves as container
        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.PointingHandCursor)
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI components."""
        # Main layout with margins for spacing between items
        main_layout = QHBoxLayout(self)
        
        # Calculate padding based on level for the OUTER layout
        # This indents the entire container box
        left_margin = 15 + (self.level * 15) + self.extra_margin
        main_layout.setContentsMargins(left_margin, 0, 15, 0)
        main_layout.setSpacing(0)
        
        # Container box that will have the background and rounded corners
        self.container = QWidget()
        self.container.setObjectName("container_box")
        self.container.setFixedHeight(50)
        container_layout = QHBoxLayout(self.container)
        
        # Inner content margins (standard padding inside the box)
        container_layout.setContentsMargins(15, 0, 15, 0)
        container_layout.setSpacing(10)
        
        # Radio button circles
        self.circle_widget = RadioCircle()
        container_layout.addWidget(self.circle_widget)
        
        # Text label
        self.text_label = QLabel(self.text)
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.text_label.setStyleSheet("background: transparent;")
        container_layout.addWidget(self.text_label, 1)
        
        # Expandable icon (if applicable)
        if self.is_expandable:
            self.expand_icon_label = QLabel()
            self.expand_icon_label.setFixedSize(20, 20)
            self.expand_icon_label.setStyleSheet("background: transparent;")
            self.update_expand_icon()
            container_layout.addWidget(self.expand_icon_label)
            
            # Setup rotation animation
            self.anim = QPropertyAnimation(self, b"rotation")
            self.anim.setDuration(200)
            self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        main_layout.addWidget(self.container)
        
        # Apply initial styling
        self.update_style()
    
    def get_rotation(self):
        return self._rotation

    def set_rotation(self, angle):
        self._rotation = angle
        self.update_expand_icon()

    rotation = Property(float, get_rotation, set_rotation)

    def update_expand_icon(self):
        """Update expand/retract icon rotation."""
        if not self.is_expandable:
            return
        
        # Always use expand.svg and rotate it
        icon = icon_manager.get_icon("expand.svg")
        pixmap = icon.pixmap(QSize(20, 20))
        
        transform = QTransform()
        transform.rotate(self._rotation)
        
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        self.expand_icon_label.setPixmap(rotated_pixmap)
    
    def update_style(self):
        """Update stylesheet based on selected state."""
        # Update circle
        self.circle_widget.set_selected(self._selected)
        
        # Check active child state
        if hasattr(self, '_has_active_child'):
             self.circle_widget.set_active_child(self._has_active_child)

        if self._selected and not self.is_expandable:
            # Active state: accent background, black text
            # NOTE: For expandable items, we DO NOT change background color even if selected usually
            # But technically expandable items are never 'selected' in the radio group sense?
            # User request: "element with child dont change background color"
            self.container.setStyleSheet(f"""
                #container_box {{
                    background-color: {colors.ACCENT};
                    border-radius: 14px;
                }}
            """)
            self.text_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors.BLACK};
                    font-family: Montserrat, Segoe UI;
                    font-size: 14px;
                    font-weight: 500;
                    background: transparent;
                }}
            """)
        else:
            # Normal state (or Expandable Active state): background color box, white text
            
            # For expandable items, we don't want hover border
            # Also, if we are in error state, we DO NOT want hover border to override error border
            hover_style = ""
            is_error = getattr(self, '_error_state', False)
            
            if not self.is_expandable and not is_error:
                hover_style = f"""
                #container_box:hover {{
                    border: 1px solid {colors.ACCENT};
                }}
                """
            
            # Check for active child state to color inner circle
            if self.is_expandable and self._has_active_child:
                  pass 
                
            self.container.setStyleSheet(f"""
                #container_box {{
                    background-color: {colors.BLACK};
                    border-radius: 13px;
                    border: { "2px solid " + colors.STATUS_DISCONNECTED if is_error else "0px solid transparent" };
                }}
                {hover_style}
            """)
            self.text_label.setStyleSheet(f"""
                QLabel {{
                    color: {colors.WHITE};
                    font-family: Montserrat, Segoe UI;
                    font-size: 14px;
                    font-weight: 500;
                    background: transparent;
                }}
            """)
            
    def flash_error(self):
        """Flash the border red."""
        self._error_state = True
        self.update_style()
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._reset_state)
        
    def _reset_state(self):
        self._error_state = False
        self.update_style()
    
    def set_selected(self, selected: bool):
        """Set selected state."""
        self._selected = selected
        self.update_style()
    
    def is_selected(self) -> bool:
        """Get selected state."""
        return self._selected
    
    def toggle_expanded(self):
        """Toggle expanded state (for expandable items)."""
        if self.is_expandable:
            self.set_expanded(not self._expanded)
            self.toggled.emit(self._expanded)
    
    def set_expanded(self, expanded: bool):
        """Set expanded state with animation."""
        self._expanded = expanded
        
        if self.is_expandable:
            start_val = self._rotation
            end_val = -90 if expanded else 0
            
            self.anim.stop()
            self.anim.setStartValue(start_val)
            self.anim.setEndValue(end_val)
            self.anim.start()

    def is_expanded(self) -> bool:
        """Get expanded state."""
        return self._expanded
    
    def set_has_active_child(self, active: bool):
        """Set active child state."""
        self._has_active_child = active
        # Directly update circle to ensure immediate feedback
        if hasattr(self.circle_widget, 'set_active_child'):
            self.circle_widget.set_active_child(active)
        self.update_style()
        self.repaint() # Force repaint of entire item logic
    
    def mousePressEvent(self, event):
        """Handle mouse clicks."""
        if event.button() == Qt.LeftButton:
            if self.is_expandable:
                # Check if click is on the arrow (right side)
                # Ensure geometry mapping is correct
                # ... (rest of logic) ...
                
                # Check if point is inside expand_icon_label
                child = self.childAt(event.pos())
                is_arrow_click = False
                if child:
                    curr = child
                    while curr:
                        if curr == self.expand_icon_label:
                            is_arrow_click = True
                            break
                        curr = curr.parentWidget()
                        if curr == self: 
                            break
                            
                if is_arrow_click:
                    self.toggle_expanded()
                else:
                    # Body click -> Default action
                    self.clicked.emit()
            else:
                self.clicked.emit()
        elif event.button() == Qt.RightButton:
            if self.on_right_click:
                self.on_right_click(event.globalPos())
        
        super().mousePressEvent(event)
