
import sys
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QRect
from PySide6.QtGui import (QColor, QPainter, QLinearGradient, QBrush, 
                         QMouseEvent, QPixmap, QPen)

from ui2 import colors, fonts

class ColorMap(QWidget):
    """
    Saturation/Value picker area.
    X-axis: Saturation (0-255)
    Y-axis: Value (255-0)
    """
    color_changed = Signal(QColor)

    def __init__(self, hue=0, parent=None):
        super().__init__(parent)
        self.hue = hue # 0-359
        self.saturation = 255
        self.value = 255
        self.setFixedSize(255, 255)
        self.setCursor(Qt.CrossCursor)
        self._cache_pixmap = None

    def set_hue(self, hue):
        self.hue = hue
        self._cache_pixmap = None
        self.update()
        self.emit_color()

    def set_sv(self, s, v):
        self.saturation = max(0, min(255, s))
        self.value = max(0, min(255, v))
        self.update()

    def get_color(self):
        return QColor.fromHsv(self.hue, self.saturation, self.value)

    def emit_color(self):
        self.color_changed.emit(self.get_color())

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw Gradient Background (Hue Color -> White horizontal, Black vertical overlay)
        # Optimized: Draw once to pixmap if hue is same, but Sat/Val overlay is complex.
        # Actually standard way: 
        # Layer 1: Horizontal Linear Gradient (White -> Hue Color)
        # Layer 2: Vertical Linear Gradient (Transparent -> Black)
        
        if not self._cache_pixmap:
            self._cache_pixmap = QPixmap(self.size())
            self._cache_pixmap.fill(Qt.transparent)
            p = QPainter(self._cache_pixmap)
            
            # Base Hue Color
            hue_color = QColor.fromHsv(self.hue, 255, 255)
            
            # Linear Horizontal: White -> Hue
            grad_h = QLinearGradient(0, 0, self.width(), 0)
            grad_h.setColorAt(0, Qt.white)
            grad_h.setColorAt(1, hue_color)
            p.fillRect(self.rect(), grad_h)
            
            # Linear Vertical: Transparent -> Black
            grad_v = QLinearGradient(0, 0, 0, self.height())
            grad_v.setColorAt(0, QColor(0, 0, 0, 0))
            grad_v.setColorAt(1, Qt.black)
            p.fillRect(self.rect(), grad_v)
            
            p.end()
            
        painter.drawPixmap(0, 0, self._cache_pixmap)
        
        # Draw Selector
        # x = saturation, y = 255 - value
        x = self.saturation
        y = 255 - self.value
        
        # Contrast circle
        painter.setPen(QPen(Qt.black, 1))
        painter.drawEllipse(QPoint(x, y), 5, 5)
        painter.setPen(QPen(Qt.white, 1))
        painter.drawEllipse(QPoint(x, y), 6, 6)

    def mousePressEvent(self, event: QMouseEvent):
        self._update_color_at_pos(event.pos())
        
    def mouseMoveEvent(self, event: QMouseEvent):
        self._update_color_at_pos(event.pos())
        
    def _update_color_at_pos(self, pos):
        x = max(0, min(255, pos.x()))
        y = max(0, min(255, pos.y()))
        
        self.saturation = x
        self.value = 255 - y
        
        self.update()
        self.emit_color()

class HueSlider(QWidget):
    """Vertical Hue Slider."""
    hue_changed = Signal(int) # 0-359

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 255)
        self.hue = 0
        self.setCursor(Qt.PointingHandCursor)

    def set_hue(self, hue):
        self.hue = max(0, min(359, hue))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Rainbow Gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        # HSV spectrum
        for i in range(7):
            val = i / 6.0
            grad.setColorAt(val, QColor.fromHsv(int(val * 359), 255, 255))
            
        painter.fillRect(self.rect(), grad)
        
        # Selector
        y = int((self.hue / 359.0) * self.height())
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, y - 2, self.width(), 4)

    def mousePressEvent(self, event):
        self._update_hue(event.y())
        
    def mouseMoveEvent(self, event):
        self._update_hue(event.y())
        
    def _update_hue(self, y):
        y = max(0, min(self.height(), y))
        self.hue = int((y / self.height()) * 359)
        self.update()
        self.hue_changed.emit(self.hue)

class ColorPickerWindow(QDialog):
    """Custom Color Picker Dialog."""
    
    color_selected = Signal(str) # Emits Hex string

    def __init__(self, initial_color="#00EAD0", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint) # Custom look
        self.setModal(True)
        self.resize(400, 350)
        
        # Styles
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.BACKGROUND};
                border: 1px solid {colors.BORDER};
                border-radius: 10px;
            }}
            QLabel {{
                color: {colors.WHITE};
                font-family: Montserrat, Segoe UI;
            }}
            QLineEdit {{
                background-color: {colors.BLACK};
                color: {colors.WHITE};
                border: 1px solid {colors.BORDER};
                border-radius: 5px;
                padding: 5px;
            }}
        """)
        
        col = QColor(initial_color)
        if not col.isValid():
             col = QColor("#00EAD0")
        
        h, s, v, _ = col.getHsv()
        if h == -1: h = 0 # Greyscale fix
        
        # Components
        self.map_widget = ColorMap(hue=h)
        self.map_widget.set_sv(s, v)
        
        self.hue_slider = HueSlider()
        self.hue_slider.set_hue(h)
        
        self.preview_box = QLabel()
        self.preview_box.setFixedSize(50, 50)
        self.preview_box.setStyleSheet("background-color: #000; border: 1px solid #333; border-radius: 5px;")
        
        self.hex_input = QLineEdit()
        self.hex_input.setMaxLength(7)
        self.hex_input.setText(initial_color.upper())
        self.hex_input.textChanged.connect(self.on_hex_input_change)
        
        # Layouts
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Top: Title
        title = QLabel("Select Accent Color")
        title.setFont(fonts.get_font(18, bold=True))
        main_layout.addWidget(title)
        
        # Middle: Map + Slider
        pickers_layout = QHBoxLayout()
        pickers_layout.addWidget(self.map_widget)
        pickers_layout.addWidget(self.hue_slider)
        main_layout.addLayout(pickers_layout)
        
        # Bottom: Hex + Preview + Buttons
        controls_layout = QHBoxLayout()
        
        input_layout = QVBoxLayout()
        input_layout.addWidget(QLabel("Hex Color:"))
        input_layout.addWidget(self.hex_input)
        controls_layout.addLayout(input_layout)
        
        controls_layout.addWidget(self.preview_box)
        controls_layout.addStretch()
        
        self.btn_ok = self.create_button("OK", self.accept_selection, is_primary=True)
        self.btn_cancel = self.create_button("Close", self.reject)
        
        controls_layout.addWidget(self.btn_ok)
        controls_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(controls_layout)
        
        # Connections
        self.hue_slider.hue_changed.connect(self.map_widget.set_hue)
        self.map_widget.color_changed.connect(self.on_map_color_changed)
        
        # Initial update
        self.on_map_color_changed(col)
        
    def create_button(self, text, callback, is_primary=False):
        btn = QPushButton(text)
        style = f"""
            QPushButton {{
                background-color: {colors.ACCENT if is_primary else colors.BLACK};
                color: {colors.BLACK if is_primary else colors.WHITE};
                border: 1px solid {colors.ACCENT if is_primary else colors.BORDER};
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors.WHITE if is_primary else '#333'};
            }}
        """
        btn.setStyleSheet(style)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        return btn

    def on_map_color_changed(self, color):
        """Update Hex and Preview from Map."""
        hex_str = color.name().upper()
        
        # Update Preview
        self.preview_box.setStyleSheet(f"background-color: {hex_str}; border: 1px solid #555; border-radius: 5px;")
        
        # Update Hex Input (block signal to prevent loop)
        self.hex_input.blockSignals(True)
        self.hex_input.setText(hex_str)
        self.hex_input.blockSignals(False)
        
        # Update OK button style live?
        # self.btn_ok.setStyleSheet(...)

    def on_hex_input_change(self, text):
        """Update Map/Slider from Hex."""
        if not text.startswith('#'):
            text = '#' + text
            
        col = QColor(text)
        if col.isValid():
            h, s, v, _ = col.getHsv()
            if h == -1: h = 0
            
            # Update Map and Slider without emitting signal back to this input
            self.map_widget.blockSignals(True)
            self.map_widget.set_hue(h)
            self.map_widget.set_sv(s, v) # This updates map visuals
            self.hue_slider.set_hue(h)
            self.map_widget.blockSignals(False)
            
            # Update Preview
            self.preview_box.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #555; border-radius: 5px;")

    def accept_selection(self):
        color_hex = self.hex_input.text()
        if not color_hex.startswith('#'): color_hex = '#' + color_hex
        
        # Basic Validation
        if QColor(color_hex).isValid():
            self.color_selected.emit(color_hex)
            self.accept()
        else:
            # Maybe flash error?
            pass
