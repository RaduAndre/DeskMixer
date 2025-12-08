"""
Custom action button widget with icon and text.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QPushButton, QHBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts


class ActionButton(QPushButton):
    """Action_button with icon and text, toggleable active state."""
    
    # Signal emitted when dropped: source_index, target_index
    dropped = Signal(int, int) 
    
    def __init__(self, icon_name: str, text: str, index: int = -1, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.button_text = text
        self.index = index # Store index for reordering
        self._is_active = False
        self.is_placeholder = False # Flag for empty slots
        self.active_variable = None
        self._reorder_mode = False
        self._drag_start_pos = None
        
        self.setFixedSize(70, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(True)
        self.setAcceptDrops(True) # Accept drops
        
        self.setup_ui()
        self.set_variable("None") # Initialize with None state
    
    def setup_ui(self):
        """Setup button UI with icon and text - vertical layout."""
        # Import QVBoxLayout
        from PySide6.QtWidgets import QVBoxLayout
        
        # Create vertical layout for center alignment
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)  # Center horizontally and vertically within the box
        
        # Icon label
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setScaledContents(False)  # Don't scale, let pixmap render at proper size
        self.update_icon()
        layout.addWidget(self.icon_label, 0, Qt.AlignHCenter)  # Explicitly center in layout
        
        # Text label
        self.text_label = QLabel(self.button_text)
        self.text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_label, 0, Qt.AlignHCenter)  # Explicitly center in layout
        
    def set_variable(self, value: str, argument: str = None, argument2: str = None):
        """Set the active variable for the button."""
        if value is None or value == "None":
            self.active_variable = None
            self.icon_name = "ghost.svg"
            self.button_text = "None" # Explicit "None" text as requested
            self._is_active = False
        else:
            self.active_variable = {'value': value, 'argument': argument, 'argument2': argument2}
            # Determine icon based on action (value)
            self.icon_name = icon_manager.get_action_icon_name(value)
            
            # Determine text
            # Use argument if present combined with value or just argument?
            if argument:
                self.button_text = argument
            else:
                self.button_text = value
                
        self.text_label.setText(self.button_text)
        self.update_icon()
        self.update_style() # Ensure style is applied (background, border, etc.)
        
    def get_variable(self):
        """Get current variable."""
        return self.active_variable

    def update_icon(self):
        """Update icon based on active state with centered rendering."""
        from PySide6.QtGui import QPixmap, QPainter
        from PySide6.QtCore import QRect
        
        # Determine target color based on activity
        # Active -> Black (on accent bg)
        # Inactive -> White (on black bg)
        if self.is_placeholder and not self._reorder_mode:
            target_color = Qt.transparent
        else:
            target_color = colors.BLACK if self._is_active else colors.WHITE
        
        # Get colored icon dynamically
        # self.icon_name holds the base name, e.g. "ghost.svg" or "play_pause.svg"
        # We NO LONGER check for _active.svg variants manually. We just color the base icon.
        # User requested: "default color ... white and on active ... black"
        icon = icon_manager.get_colored_icon(self.icon_name, target_color)
        
        # Create a square pixmap to ensure centering
        size = 24
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        # Paint the icon centered in the square pixmap
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Draw icon centered in the square
        icon.paint(painter, 0, 0, size, size)
        painter.end()
        
        self.icon_label.setPixmap(pixmap)
        
    def update_style(self):
        """Update stylesheet based on active state."""
        # Only allow active styling if we have a variable set (not None/ghost)
        show_active = self._is_active
        if self.is_placeholder:
             # Placeholder Style (Normal Mode) -> Invisible but takes space
             self.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
             """)
             # Hide contents
             self.icon_label.hide()
             self.text_label.hide()
        elif show_active:
            # Active state: accent background, no border
            self.icon_label.show()
            self.text_label.show()
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors.ACCENT};
                    border: none;
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    background-color: {colors.ACCENT};
                }}
                QLabel {{
                    color: {colors.BLACK};
                    font-family: Montserrat, Segoe UI;
                    font-size: 10px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
        else:
            # Normal state: black background, border
            self.icon_label.show()
            self.text_label.show()
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {colors.BLACK};
                    border: 1px solid {colors.BORDER};
                    border-radius: 18px;
                }}
                QPushButton:hover {{
                    background-color: #1a1a1a;
                    border: 1px solid {colors.ACCENT};
                }}
                QLabel {{
                    color: {colors.WHITE};
                    font-family: Montserrat, Segoe UI;
                    font-size: 10px;
                    font-weight: bold;
                    background: transparent;
                    border: none;
                }}
            """)
        
        self.update_icon()
        self.adjust_font_size()
    
    def set_active(self, active: bool):
        """Set active state and update appearance."""
        self._is_active = active
        self.setChecked(active)
        self.update_style()
    
    def toggle_active(self):
        """Toggle active state."""
        # Always allow toggle
        self.set_active(not self._is_active)
    
    def is_active(self) -> bool:
        """Get active state."""
        return self._is_active
    
    def mousePressEvent(self, event):
        """Handle mouse press to toggle state or start drag."""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            if not self._reorder_mode:
                 self.toggle_active()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle drag start."""
        if not self._reorder_mode or not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
            
        if not self._drag_start_pos:
            return
            
        # Check drag distance
        if (event.pos() - self._drag_start_pos).manhattanLength() < 10: # Application.startDragDistance
            return
            
        # Start Drag
        from PySide6.QtGui import QDrag
        from PySide6.QtCore import QMimeData
        
        drag = QDrag(self)
        mime = QMimeData()
        # Store index as text or custom format
        mime.setText(str(self.index))
        # Add a custom format to identify it's a button reorder
        mime.setData("application/x-deskmixer-button", str(self.index).encode())
        drag.setMimeData(mime)
        
        # Determine pixmap for drag
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        
        drag.exec_(Qt.MoveAction)
        
    def dragEnterEvent(self, event):
        if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-button"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
         if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-button"):
            event.acceptProposedAction()
         else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-button"):
            source_idx = int(event.mimeData().text())
            target_idx = self.index
            
            if source_idx != target_idx:
                self.dropped.emit(source_idx, target_idx)
                
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def set_reorder_mode(self, enabled: bool):
        self._reorder_mode = enabled
        # Update cursor or style if needed
        # User requested "snap animation" - handled by layout update in parent
        if enabled:
            # Maybe dashed border?
            if self.is_placeholder:
                self.setStyleSheet(self.styleSheet() + "\nQPushButton { border: 2px dashed #666; background: transparent; }")
                # Ensure contents are hidden (should be handled by update_style call or sticky state)
                self.icon_label.hide()
                self.text_label.hide()
            else:
                pass # Real buttons get no visual change, but are draggable
            
            # Update icon anyway in case we want to show/hide it
            self.update_icon()
            
        else:
            self.update_style() # Reset style
            self.update_icon()

    def adjust_font_size(self):
        """Adjust font size to fit within the button width."""
        import PySide6.QtGui as QtGui
        
        # Available width (button width - margins)
        # Button is 70px wide, margins 5px each side -> 60px
        # Let's say safe width is 58px
        max_width = 58
        
        font = self.text_label.font()
        font.setFamily("Montserrat") # Ensure family
        font_size = 10 # Start with default
        
        # Loop to find fitting size
        while font_size > 5: # Minimum readable size
            font.setPixelSize(font_size)
            metrics = QtGui.QFontMetrics(font)
            text_width = metrics.horizontalAdvance(self.button_text)
            
            if text_width <= max_width:
                break
            
            font_size -= 1
        
        # Apply specific style to label, overriding parent style if needed
        # We need to maintain color based on active state
        if self.is_placeholder and not self._reorder_mode:
             text_color = Qt.transparent
        else:
             text_color = colors.BLACK if self._is_active else colors.WHITE
        
        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-family: Montserrat, Segoe UI;
                font-size: {font_size}px;
                font-weight: bold;
                background: transparent;
                border: none;
            }}
        """)
