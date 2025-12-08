"""
Custom volume slider widget with vertical slider and name label.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel, QSlider
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPainterPath
from ui2.icon_manager import icon_manager
from ui2 import colors, fonts


class CustomSlider(QSlider):
    """Custom vertical slider with rounded track, fill, and scale icon."""
    
    # Signal to notify parent when clicked
    clicked = Signal()
    
    def __init__(self, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(50)
        self.setFixedWidth(90)  # Wider to accommodate slider head without cropping
        self.setMinimumHeight(200)  # Increased minimum height for larger sliders
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)  # Enable hover tracking
        
        # Load icons
        self.normal_icon = icon_manager.get_icon("slider_head.svg")
        self.active_icon = icon_manager.get_active_icon("slider_head.svg")
        self.hover_icon = icon_manager.get_active_icon("slider_head.svg")  # Use active icon for hover
        self.scale_icon = icon_manager.get_icon("scale.svg")
        self._is_active = False
        self._is_hovered = False
    
    def set_active(self, active: bool):
        """Set active state."""
        self._is_active = active
        self.update()
    
    def set_hover(self, hover: bool):
        """Set hover state."""
        self._is_hovered = hover
        self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def paintEvent(self, event):
        """Custom paint for scale icon, rounded track, fill, and slider head."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Calculate dimensions
        track_width = 20
        track_height = self.height() - 30  # Leave space for slider head at top/bottom (15px each)
        track_y = 15  # Top margin
        
        # Center the track horizontally in the widget
        track_x = (self.width() - track_width) // 2
        
        # Draw scale icon to the left of the track, 94% as tall as track
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QRectF
        
        scale_width = 10
        scale_height = int(track_height * 0.94)  # 94% of track height
        scale_x = track_x - scale_width - 2  # 2px gap from track
        scale_y = track_y + (track_height - scale_height) // 2  # Center vertically
        
        # Use SVG renderer for precise control
        scale_path = icon_manager.get_icon_path("scale.svg")
        if os.path.exists(scale_path):
            svg_renderer = QSvgRenderer(scale_path)
            svg_renderer.render(painter, QRectF(scale_x, scale_y, scale_width, scale_height))
        
        # Draw background track (black with rounded corners)
        track_rect = QPainterPath()
        track_rect.addRoundedRect(track_x, track_y, track_width, track_height, 10, 10)
        painter.fillPath(track_rect, QColor(colors.BLACK))
        
        # Calculate slider position
        value_ratio = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        slider_y = track_y + track_height - (value_ratio * track_height)
        
        # Draw fill (white from bottom to slider position)
        if value_ratio > 0:
            fill_height = value_ratio * track_height
            fill_rect = QPainterPath()
            fill_rect.addRoundedRect(track_x, track_y + track_height - fill_height, 
                                    track_width, fill_height, 10, 10)
            painter.fillPath(fill_rect, QColor(colors.WHITE))
        
        # Draw slider head icon (2.5x wider than track for better visibility)
        # Use active icon if active, hover icon if hovered, otherwise normal
        if self._is_active:
            icon = self.active_icon
        elif self._is_hovered:
            icon = self.hover_icon
        else:
            icon = self.normal_icon
        icon_size = int(track_width * 2.5)  # 2.5x the track width
        icon_x = (self.width() - icon_size) // 2
        icon_y = int(slider_y - icon_size // 2)
        icon.paint(painter, icon_x, icon_y, icon_size, icon_size)
        
        painter.end()


class VolumeSlider(QWidget):
    """Volume slider component with scale icon, slider, and name label."""
    
    clicked = Signal()  # Signal when slider is clicked (for menu opening)
    valueChanged = Signal(int)  # Signal when value changes
    dropped = Signal(int, int) # Signal emitted when dropped
    variableChanged = Signal(list) # Signal when variable changes
    
    def __init__(self, name: str = "Volume", index: int = -1, parent=None):
        super().__init__(parent)
        self.name = name
        self.index = index
        self._is_selected = False
        self._reorder_mode = False
        self._drag_start_pos = None
        
        # Variable tracking
        # Each item is a dictionary: {'value': str, 'argument': str|None}
        self.active_variables = [] 
        
        # Enable styled background to support border/background stylesheets
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setup_ui()
        self.update_label() # Initial label update
        
    def set_variables(self, variables: list):
        """Set multiple variables (list of strings or dicts)."""
        self.active_variables = []
        for var in variables:
            if isinstance(var, dict):
                self.active_variables.append(var)
            elif isinstance(var, str):
                self.active_variables.append({'value': var, 'argument': None})
        self.update_label()
        self.variableChanged.emit(self.active_variables)

    def add_variable(self, value: str, argument: str = None):
        """Add a variable to the slider."""
        # Check if already exists
        if self.has_variable(value, argument):
            return
        
        self.active_variables.append({'value': value, 'argument': argument})
        self.update_label()
        self.variableChanged.emit(self.active_variables)
        
    def remove_variable(self, value: str, argument: str = None):
        """Remove a variable from the slider."""
        self.active_variables = [
            var for var in self.active_variables 
            if not (var['value'] == value and var['argument'] == argument)
        ]
        self.update_label()
        self.variableChanged.emit(self.active_variables)
        
    def toggle_variable(self, value: str, argument: str = None):
        """Toggle a variable."""
        if self.has_variable(value, argument):
            self.remove_variable(value, argument)
        else:
            self.add_variable(value, argument)

    def has_variable(self, value: str, argument: str = None) -> bool:
        """Check if variable is active."""
        for var in self.active_variables:
            if var['value'] == value and var['argument'] == argument:
                return True
        return False
        
    def update_label(self):
        """Update label text based on active variables."""
        if not self.active_variables:
            self.name_label.setText("None")
            return
            
        parts = []
        for var in self.active_variables:
            # Use argument if present, else value
            # e.g. Mute -> Microphone: "Microphone"
            # e.g. Master: "Master"
            arg = var.get('argument')
            val = var.get('value')
            
            if arg:
                parts.append(arg)
            elif val:
                parts.append(val)
        
        if not parts:
            self.name_label.setText("None")
        else:
            # Space separated as requested "Master Microphone"
            text = " ".join(parts)
            self.name_label.setText(text)
            
            # Auto-shrink font logic for single words
            # Reset font first
            font = self.name_label.font()
            font.setPointSize(fonts.SLIDER_NAME_SIZE) # Default size
            self.name_label.setFont(font)
            
            if len(parts) == 1:
                # Single word - enable auto-shrink
                from PySide6.QtGui import QFontMetrics
                
                # Available width (90px fixed width - padding)
                # Padding defined in stylesheet is 5px (left+right = 10px)
                # Border 1px * 2 = 2px
                available_width = 90 - 12 
                
                fm = QFontMetrics(font)
                while fm.horizontalAdvance(text) > available_width and font.pointSize() > 6:
                    font.setPointSize(font.pointSize() - 1)
                    fm = QFontMetrics(font)
                
                self.name_label.setFont(font)
            else:
                 # Multi-word - ensure word wrap is ON (already set in setup_ui)
                 # and font is default
                 pass

    def setup_ui(self):
        """Setup the UI components."""
        # Use grid layout: 2 rows, 1 column
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # No spacing between rows
        # No column stretch - use fixed sizes for compact layout
        # Set row stretch: 80% for slider (row 0), 20% for text (row 1)
        layout.setRowStretch(0, 8)  # 80%
        layout.setRowStretch(1, 2)  # 20%
        
        # Row 0: Slider container (takes 80% of height)
        slider_container = QWidget()

        slider_layout = QVBoxLayout(slider_container)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_layout.setAlignment(Qt.AlignCenter)  # Center slider vertically and horizontally
        
        self.slider = CustomSlider()
        self.slider.valueChanged.connect(self.valueChanged.emit)
        self.slider.clicked.connect(self.clicked.emit)
        slider_layout.addWidget(self.slider)
        
        layout.addWidget(slider_container, 0, 0, Qt.AlignHCenter)
        
        # Row 1: Text box container (flexible height, text aligned top)
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)  # Top-aligned, centered horizontally
        
        self.name_label = QLabel(self.name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setFixedWidth(90)  # Fixed width matching slider width
        self.update_label_style(False)
        text_layout.addWidget(self.name_label)
        
        layout.addWidget(text_container, 1, 0, Qt.AlignHCenter | Qt.AlignTop)
        
        # Set cursor and enable mouse tracking for hover
        self.setCursor(Qt.PointingHandCursor)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAcceptDrops(True) # Accept drops

    def mousePressEvent(self, event):
        """Emit clicked signal when widget is clicked, or start drag in reorder mode."""
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            if not self._reorder_mode:
                 self.clicked.emit()
            
            # CRITICAL: Accept event to prevent propagation to parent
            # causing background click handler to cancel reorder mode.
            event.accept()
            
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        """Handle drag start."""
        if not self._reorder_mode or not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
            
        if not self._drag_start_pos:
            return
            
        # Check drag distance
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < 10:
            return
            
        # Start Drag
        from PySide6.QtGui import QDrag
        from PySide6.QtCore import QMimeData
        
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.index))
        mime.setData("application/x-deskmixer-slider", str(self.index).encode())
        drag.setMimeData(mime)
        
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint() - self.rect().topLeft()) # Approximate hotspot
        
        drag.exec(Qt.MoveAction)
        
    def dragEnterEvent(self, event):
        if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-slider"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
         if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-slider"):
            event.acceptProposedAction()
         else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if self._reorder_mode and event.mimeData().hasFormat("application/x-deskmixer-slider"):
            source_idx = int(event.mimeData().text())
            target_idx = self.index
            
            if source_idx != target_idx:
                self.dropped.emit(source_idx, target_idx)
                
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
            
    def set_reorder_mode(self, enabled: bool):
        self._reorder_mode = enabled
        # Disable interaction with inner slider and other children to allow drag from anywhere
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False) # Ensure self is NOT transparent
        
        # Recursively set transparency for all children
        def set_transparent(widget, transparent):
            widget.setAttribute(Qt.WA_TransparentForMouseEvents, transparent)
            for child in widget.findChildren(QWidget):
                set_transparent(child, transparent)
                
        # We only want to set children transparent, not self
        for child in self.findChildren(QWidget):
             set_transparent(child, enabled)
             
        if enabled:
            # Dashed border style with slight background to indicate selection area
            # Ensure WA_StyledBackground is set so QWidget supports stylesheets
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setStyleSheet(self.styleSheet() + "\nVolumeSlider { border: 2px dashed #888; border-radius: 5px; background: rgba(255, 255, 255, 0.05); }")
        else:
            # Reset style
             self.setStyleSheet("") 
 
             
    def update_label_style(self, hover: bool):
        """Update label style based on hover state."""
        border_settings = ""
        
        if getattr(self, '_error_state', False):
             border_color = colors.STATUS_DISCONNECTED # Red
             border_settings = f"border: 2px solid {border_color};"
        elif getattr(self, '_success_state', False):
             border_color = colors.STATUS_CONNECTED # Green
             border_settings = f"border: 2px solid {border_color};"
        else:
             border_color = colors.ACCENT if hover or self._is_selected else colors.WHITE
             border_settings = f"border: 1px solid {border_color};"
             
        self.name_label.setStyleSheet(f"""
            QLabel {{
                {fonts.slider_name_style()}
                {border_settings}
                border-radius: 5px;
                padding: 5px;
            }}
        """)

    def flash_error(self):
        """Flash the border red to indicate error."""
        self._error_state = True
        self.update_label_style(False)
        
        # Reset after 500ms
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._reset_state)
        
    def flash_success(self):
        """Flash the border green to indicate success/ownership."""
        self._success_state = True
        self.update_label_style(False)
        
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, self._reset_state)
        
    def _reset_state(self):
        """Reset error/success state."""
        self._error_state = False
        self._success_state = False
        self.update_label_style(self.underMouse())
    
    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        if not self._is_selected:  # Only show hover if not already active
            self.slider.set_hover(True)
            self.update_label_style(True)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave to remove hover effect."""
        if not self._is_selected:  # Only remove hover if not active
            self.slider.set_hover(False)
            self.update_label_style(False)
        super().leaveEvent(event)
    
    # mousePressEvent replaced/overridden above
    # def mousePressEvent(self, event):
    #     """Emit clicked signal when widget is clicked."""
    #     if event.button() == Qt.LeftButton:
    #         self.clicked.emit()
    #     super().mousePressEvent(event)
    
    def set_active(self, active: bool):
        """Set active/selected state."""
        self._is_selected = active
        self.slider.set_active(active)
        
        if active:
            # When activating, set accent border
            self.update_label_style(True)
        else:
            # When deactivating, check if mouse is still over widget
            # to determine if we should show hover or normal state
            is_under_mouse = self.underMouse()
            self.slider.set_hover(is_under_mouse)
            self.update_label_style(is_under_mouse)
        
        # Force immediate update
        self.slider.update()
        self.update()
    
    def set_value(self, value: int):
        """Set slider value."""
        self.slider.setValue(value)
    
    def get_value(self) -> int:
        """Get current slider value."""
        return self.slider.value()
