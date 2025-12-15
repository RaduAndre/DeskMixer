"""
Browse menu item with text label and search icon.
"""

import sys
import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtGui import QFontMetrics, QColor
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts
from ui2.file_utils import browse_app_file
# Reuse RadioCircle if possible, otherwise we might need to duplicate or move it to a shared file.
# Assuming we can import it or should I duplicate for independence?
# Importing is cleaner.
from ui2.components.menu_item import RadioCircle

class BrowseItem(QWidget):
    """Menu item with a browse button/icon."""
    
    app_selected = Signal(str, str) # Emits (app_name, app_path)
    clicked = Signal() # Signal for activation via parent
    
    def __init__(self, initial_text: str = "Browse an app", initial_value: str = "", level: int = 0, parent=None):
        super().__init__(parent)
        self.default_text = "Browse an app"
        self.current_text = initial_value if initial_value else self.default_text
        self.current_path = None # Initializes as None, will be set on browse or passed if needed
        self.level = level
        self._active = False
        
        # Make the main widget transparent
        self.setStyleSheet("background: transparent;")
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup UI components."""
        main_layout = QHBoxLayout(self)
        
        # Calculate padding based on level (same logic as MenuItem/InputItem)
        left_margin = 15 + (self.level * 15) + 20 # Extra indent for child
        main_layout.setContentsMargins(left_margin, 0, 15, 0)
        main_layout.setSpacing(0)
        
        # Container box
        self.container = QWidget()
        self.container.setObjectName("container_box")
        self.container.setFixedHeight(50)
        
        
        # self.update_style() moved to end
        
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(15, 0, 15, 0)
        container_layout.setSpacing(10)
        
        # Radio circle
        self.circle_widget = RadioCircle()
        # If we want the circle to show active state when item is active
        self.circle_widget.set_selected(False) # Always false initially? 
        # Actually, if it's active, maybe we show it?
        # User said: "item will only activate once it was selected an app"
        container_layout.addWidget(self.circle_widget)
        
        # Text Label
        self.text_label = QLabel()
        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: {colors.WHITE};
                font-family: Montserrat, Segoe UI;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
        """)
        self.set_text_safe(self.current_text)
        container_layout.addWidget(self.text_label, 1)
        
        # Search Icon (Right side)
        self.search_icon = QLabel()
        self.search_icon.setFixedSize(20, 20)
        self.search_icon.setStyleSheet("background: transparent;")
        self.search_icon.setCursor(Qt.PointingHandCursor)
        
        self.update_icon_style(hover=False)
        
        # Install event filter or subclass for hover? 
        # Easier to just use enter/leave event on the label if it was a custom widget,
        # but QLabel doesn't easily support hover style changes for the pixmap without events.
        self.search_icon.installEventFilter(self)
        
        container_layout.addWidget(self.search_icon)
        
        main_layout.addWidget(self.container)
        
        # Apply initial styling after all components created
        self.update_style()

    def eventFilter(self, obj, event):
        if obj == self.search_icon:
            if event.type() == QEvent.Enter:
                self.update_icon_style(hover=True)
                return True
            elif event.type() == QEvent.Leave:
                self.update_icon_style(hover=False)
                return True
            elif event.type() == QEvent.MouseButtonPress:
                self.browse_app()
                return True
        return super().eventFilter(obj, event)

    def update_icon_style(self, hover: bool):
        # Default: White
        # Hover: Accent (if not active)
        # Active: Black
        
        if self._active:
            # If active, background is Acccent, so icon must be Black.
            # Hovering on active item usually doesn't change color, or maybe stays black.
            color = colors.BLACK
        else:
            color = colors.ACCENT if hover else colors.WHITE
            
        icon = icon_manager.get_colored_icon("search.svg", color)
        self.search_icon.setPixmap(icon.pixmap(20, 20))

    def set_text_safe(self, text):
        """Set text with elision if needed."""
        # We need the width of the label to know how much to elide.
        # Initial setup might not have width.
        # But we can try using QFontMetrics.
        
        current_font = self.text_label.font()
        metrics = QFontMetrics(current_font)
        
        # Approximate available width: 
        # Container width (let's assume parent width or fixed?) - margins - circle - icon
        # This is tricky without resize event.
        # For now, let's just set text, and handle resize event if we want dynamic elision.
        # Or just elide to a safe max width (e.g. 200px)
        
        elided = metrics.elidedText(text, Qt.ElideRight, 200) # Temporary fixed width
        self.text_label.setText(elided)
        self.text_label.setToolTip(text) # Full text on hover

    def browse_app(self):
        """Simulate browsing an app."""
        # Use util function
        if hasattr(self, 'parentWidget'):
            parent = self.parentWidget()
        else:
            parent = self
            
        app_path, app_name = browse_app_file(parent)
        
        if app_path:
             self.current_text = app_name
             self.current_path = app_path
             self.set_text_safe(self.current_text)
             # "item will only activate once it was selected an app"
             self.set_active(True)
             self.app_selected.emit(app_name, app_path)
        else:
             # Cancelled or error
             pass

    def set_active(self, active: bool):
        self._active = active
        self.update_style()
        self.circle_widget.set_selected(active) # Also update the dot? usually yes for leaf items
        
    def set_selected(self, selected: bool):
        """Compat alias."""
        self.set_active(selected)
        
    def is_selected(self):
        return self._active

    def update_style(self):
        # Update text color
        text_color = colors.BLACK if self._active else colors.WHITE
        self.text_label.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-family: Montserrat, Segoe UI;
                font-size: 14px;
                font-weight: 500;
                background: transparent;
            }}
        """)
        
        # Update Container
        if self._active:
             # Active: Accent background, No border? Or maybe transparent border to keep layout?
             # MenuItem uses accent background.
             self.container.setStyleSheet(f"""
                #container_box {{
                    background-color: {colors.ACCENT};
                    border-radius: 13px;
                    border: 0px solid transparent; 
                }}
             """)
        else:
             # Inactive: Black background, Transparent border (initially) -> Accent on hover
             self.container.setStyleSheet(f"""
                #container_box {{
                    background-color: {colors.BLACK};
                    border-radius: 13px;
                    border: 0px solid transparent;
                }}
                #container_box:hover {{
                    border: 1px solid {colors.ACCENT};
                }}
             """)
             
        # Update icon color (force update based on new active state)
        # We assume not hovering when state changes programmatically, or we wait for mouse event.
        # But we should ensure it's correct immediately.
        self.update_icon_style(hover=False) 
        
        # Update circle
        # Update circle
        if hasattr(self, 'circle_widget'):
            self.circle_widget.set_selected(self._active)
            
        self.style().unpolish(self.container)
        self.style().polish(self.container)
        
    def resizeEvent(self, event):
        # Handle dynamic elision
        # container width - margins (15+15) - spacing(10+10) - circle(20) - icon(20)
        # approximate available width for label
        if hasattr(self, 'text_label'):
             available_width = self.container.width() - 30 - 20 - 20 - 20 - 10 
             # 30 margin, 20 circle, 10 space, 10 space, 20 icon -> approx
             if available_width > 0:
                 current_font = self.text_label.font()
                 metrics = QFontMetrics(current_font)
                 elided = metrics.elidedText(self.current_text, Qt.ElideRight, available_width)
                 self.text_label.setText(elided)
        super().resizeEvent(event)
