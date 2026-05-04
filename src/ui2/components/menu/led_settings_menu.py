"""
LED Settings Menu Component
Handles LED brightness, style, and colour configuration.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QSlider, QPushButton, QSizePolicy, QStackedWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from ui2 import colors, fonts
from ui2.settings_manager import settings_manager


# ── Helper: hex ↔ [R, G, B] ──────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> list:
    """Convert '#RRGGBB' to [R, G, B]."""
    try:
        c = QColor(hex_color)
        return [c.red(), c.green(), c.blue()]
    except Exception:
        return [0, 61, 61]


def _rgb_to_hex(rgb: list) -> str:
    """Convert [R, G, B] to '#RRGGBB'."""
    try:
        return QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])).name().upper()
    except Exception:
        return "#003D3D"


# ── Small branded slider inside an outlined box ───────────────────────────────

class BrightnessSliderRow(QWidget):
    """
    Outlined box that contains:
      [value label]  [────────────────slider──────────────────]
    Styled with the accent colour border.
    """
    value_changed = Signal(int)

    def __init__(self, initial: int = 80, min_val: int = 0, max_val: int = 100,
                 fmt: str = "{v}%", parent=None):
        super().__init__(parent)
        self._fmt = fmt
        self._build(initial, min_val, max_val)

    def _build(self, initial: int, min_val: int = 0, max_val: int = 100):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(0)

        box = QWidget()
        box.setObjectName("bright_box")
        self._box = box
        row = QHBoxLayout(box)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(10)

        # Value label on the left
        self._lbl = QLabel(self._fmt.format(v=initial))
        self._lbl.setFixedWidth(36)
        self._lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lbl.setFont(fonts.get_font(12, bold=True))
        self._lbl.setStyleSheet(f"color: {colors.ACCENT}; background: transparent; border: none;")

        # Slider
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(initial)
        self._slider.setCursor(Qt.PointingHandCursor)

        self._slider.valueChanged.connect(self._on_value)

        row.addWidget(self._lbl)
        row.addWidget(self._slider, 1)
        outer.addWidget(box)

        self._refresh_style()

    def _on_value(self, v: int):
        self._lbl.setText(self._fmt.format(v=v))
        self.value_changed.emit(v)

    def _refresh_style(self):
        accent = colors.ACCENT
        self._box.setStyleSheet(f"""
            QWidget#bright_box {{
                border: 1px solid {accent};
                border-radius: 6px;
                background: transparent;
            }}
        """)
        self._lbl.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
        self._slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background: {colors.BORDER};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {accent};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {accent};
            }}
            QSlider::handle:horizontal:hover {{
                background: {colors.WHITE};
            }}
        """)

    def get_value(self) -> int:
        return self._slider.value()


# ── Colour swatch button ───────────────────────────────────────────────────────

class ColorSwatchButton(QPushButton):
    """A small square showing the current colour; click to open colour picker."""

    color_changed = Signal(str)   # emits '#RRGGBB'

    def __init__(self, initial_hex: str = "#003D3D", label: str = "", parent=None):
        super().__init__(parent)
        self._hex = initial_hex
        self._label = label
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._apply_style()
        self.clicked.connect(self._open_picker)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._hex};
                border: 2px solid {colors.BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid {colors.ACCENT};
            }}
        """)

    def set_color(self, hex_color: str):
        self._hex = hex_color
        self._apply_style()

    def get_color(self) -> str:
        return self._hex

    def _open_picker(self):
        from ui2.color_picker import ColorPickerWindow
        parent = self
        while parent and not parent.isWindow():
            parent = parent.parentWidget()
        dlg = ColorPickerWindow(initial_color=self._hex, parent=parent)
        dlg.color_selected.connect(self._on_picked)
        dlg.exec()

    def _on_picked(self, hex_color: str):
        self.set_color(hex_color)
        self.color_changed.emit(hex_color)


# ── Generic style selector row ────────────────────────────────────────────────────────

def _style_item_style(selected: bool) -> str:
    bg   = colors.ACCENT if selected else "transparent"
    fg   = colors.BACKGROUND if selected else colors.WHITE
    bdr  = colors.ACCENT
    return f"""
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 1px solid {bdr};
            border-radius: 4px;
            padding: 3px 10px;
            font-family: Montserrat, Segoe UI;
            font-size: 11px;
        }}
        QPushButton:hover {{
            background: {colors.ACCENT};
            color: {colors.BACKGROUND};
        }}
    """

class GenericSelector(QWidget):
    """Row of pill-buttons for choosing from a list of options."""
    selection_changed = Signal(int)

    def __init__(self, options: list, current: int = 0, parent=None):
        super().__init__(parent)
        self._current = current
        self._btns = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)
        for i, name in enumerate(options):
            btn = QPushButton(name)
            btn.setCheckable(False)
            btn.setStyleSheet(_style_item_style(i == current))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx))
            layout.addWidget(btn)
            self._btns.append(btn)
        layout.addStretch()

    def _select(self, idx: int):
        if idx != self._current:
            self._current = idx
            for i, btn in enumerate(self._btns):
                btn.setStyleSheet(_style_item_style(i == idx))
            self.selection_changed.emit(idx)

    def get_value(self) -> int:
        return self._current


# ── Colour selector block (handles All vs By Slider) ─────────────────────────────────────

class ColorSelectorBlock(QWidget):
    colors_changed = Signal(list)
    
    def __init__(self, initial_colors, label_prefix, is_all_mode=False, parent=None):
        super().__init__(parent)
        self.label_prefix = label_prefix
        self.num_colors = len(initial_colors)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # Page 0: Single color (All mode)
        self.page_all = QWidget()
        l_all = QHBoxLayout(self.page_all)
        l_all.setContentsMargins(12, 4, 12, 4)
        col_all = QVBoxLayout()
        lbl_all = QLabel("All")
        lbl_all.setStyleSheet(f"color: {colors.WHITE}; font-size: 10px; background:transparent; border:none;")
        lbl_all.setAlignment(Qt.AlignHCenter)
        # Use the first color for "all"
        self.swatch_all = ColorSwatchButton(initial_hex=_rgb_to_hex(initial_colors[0]))
        self.swatch_all.color_changed.connect(self._on_all_changed)
        col_all.addWidget(lbl_all, 0, Qt.AlignHCenter)
        col_all.addWidget(self.swatch_all, 0, Qt.AlignHCenter)
        l_all.addLayout(col_all)
        l_all.addStretch()
        self.stack.addWidget(self.page_all)
        
        # Page 1: Multi colors
        self.page_multi = QWidget()
        l_multi = QHBoxLayout(self.page_multi)
        l_multi.setContentsMargins(12, 4, 12, 4)
        l_multi.setSpacing(8)
        self._swatches = []
        for i, rgb in enumerate(initial_colors):
            col = QVBoxLayout()
            lbl = QLabel(f"{label_prefix}{i+1}")
            lbl.setStyleSheet(f"color: {colors.WHITE}; font-size: 10px; background:transparent; border:none;")
            lbl.setAlignment(Qt.AlignHCenter)
            sw = ColorSwatchButton(initial_hex=_rgb_to_hex(rgb))
            sw.color_changed.connect(lambda h, idx=i: self._on_multi_changed(idx, h))
            col.addWidget(lbl, 0, Qt.AlignHCenter)
            col.addWidget(sw, 0, Qt.AlignHCenter)
            l_multi.addLayout(col)
            self._swatches.append(sw)
        l_multi.addStretch()
        self.stack.addWidget(self.page_multi)
        
        self.set_mode(is_all_mode)
        
    def set_mode(self, is_all_mode: bool):
        self.stack.setCurrentIndex(0 if is_all_mode else 1)
        
    def _on_all_changed(self, hex_color: str):
        rgb = _hex_to_rgb(hex_color)
        res = [rgb] * self.num_colors
        # Sync multi swatches to match the new "all" color
        for sw in self._swatches:
            sw.set_color(hex_color)
        self.colors_changed.emit(res)
        
    def _on_multi_changed(self, idx: int, hex_color: str):
        res = [_hex_to_rgb(sw.get_color()) for sw in self._swatches]
        # Sync the "all" swatch to the first item
        if idx == 0:
            self.swatch_all.set_color(hex_color)
        self.colors_changed.emit(res)


# ── Section label ─────────────────────────────────────────────────────────────

def _make_row_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color: {colors.WHITE};
        font-family: Montserrat, Segoe UI;
        font-size: 12px;
        background: transparent;
        border: none;
        padding-left: 12px;
        padding-top: 6px;
    """)
    return lbl


# ── Main LED settings menu ────────────────────────────────────────────────────

class LedSettingsMenu:
    """Builds the LEDs section inside the settings menu."""

    def __init__(self, menu_builder):
        self.menu_builder = menu_builder

    def build_section(self, board_comm=None):
        """Append a 'LEDs' section to the currently open settings menu."""
        self.menu_builder.add_head("LEDs")

        layout = self.menu_builder.sections["LEDs"]["layout"]
        self._board_comm = board_comm

        # ── Brightness ────────────────────────────────────────────────
        layout.addWidget(_make_row_label("LED Brightness"))
        self.brightness_slider = BrightnessSliderRow(
            initial=settings_manager.get_led_brightness(),
            min_val=0, max_val=100, fmt="{v}%")
        self.brightness_slider.value_changed.connect(self._on_brightness)
        layout.addWidget(self.brightness_slider)

        # ── Animation Speed ───────────────────────────────────────────
        layout.addWidget(_make_row_label("Animation Speed"))
        self.anim_speed_slider = BrightnessSliderRow(
            initial=settings_manager.get_led_anim_speed(),
            min_val=1, max_val=10, fmt="{v}")
        self.anim_speed_slider.value_changed.connect(self._on_anim_speed)
        layout.addWidget(self.anim_speed_slider)

        # ── Sliders ──────────────────────────────────────────────────
        layout.addWidget(_make_row_label("Slider Fill"))
        self.slider_fill = GenericSelector(["None", "Full", "Volume based"], current=settings_manager.get_slider_led_fill())
        layout.addWidget(self.slider_fill)

        self.lbl_s_style = _make_row_label("Slider Style")
        layout.addWidget(self.lbl_s_style)
        self.slider_style = GenericSelector(["Surf", "Solid", "Pulse", "VU Bar", "Starlight"], current=settings_manager.get_slider_led_style())
        layout.addWidget(self.slider_style)

        self.lbl_s_mode = _make_row_label("Slider Color Mode")
        layout.addWidget(self.lbl_s_mode)
        s_mode_str = settings_manager.get_slider_color_mode()
        self.slider_mode = GenericSelector(["All", "By slider"], current=0 if s_mode_str == "all" else 1)
        layout.addWidget(self.slider_mode)

        self.lbl_s_color = _make_row_label("Slider Color")
        layout.addWidget(self.lbl_s_color)
        s_colors = settings_manager.get_slider_led_colors()
        while len(s_colors) < 5:
            s_colors.append([0, 61, 61])
        self.slider_colors = ColorSelectorBlock(s_colors[:5], "S", is_all_mode=(s_mode_str=="all"))
        layout.addWidget(self.slider_colors)

        self.slider_fill.selection_changed.connect(self._on_slider_fill)
        self.slider_style.selection_changed.connect(self._on_slider_style)
        self.slider_mode.selection_changed.connect(self._on_slider_mode)
        self.slider_colors.colors_changed.connect(self._on_slider_colors)

        # ── Buttons ──────────────────────────────────────────────────
        layout.addWidget(_make_row_label("Button Fill"))
        self.button_fill = GenericSelector(["None", "On press", "Always"], current=settings_manager.get_button_led_fill())
        layout.addWidget(self.button_fill)

        self.lbl_b_style = _make_row_label("Button Style")
        layout.addWidget(self.lbl_b_style)
        self.button_style = GenericSelector(["Surf", "Solid", "Pulse", "VU Bar", "Starlight"], current=settings_manager.get_button_led_style())
        layout.addWidget(self.button_style)

        self.lbl_b_mode = _make_row_label("Button Color Mode")
        layout.addWidget(self.lbl_b_mode)
        b_mode_str = settings_manager.get_button_color_mode()
        self.button_mode = GenericSelector(["All", "By button"], current=0 if b_mode_str == "all" else 1)
        layout.addWidget(self.button_mode)

        self.lbl_b_color = _make_row_label("Button Color")
        layout.addWidget(self.lbl_b_color)
        b_colors = settings_manager.get_button_led_colors()
        while len(b_colors) < 6:
            b_colors.append([61, 20, 0])
        self.button_colors = ColorSelectorBlock(b_colors[:6], "B", is_all_mode=(b_mode_str=="all"))
        layout.addWidget(self.button_colors)

        self.button_fill.selection_changed.connect(self._on_button_fill)
        self.button_style.selection_changed.connect(self._on_button_style)
        self.button_mode.selection_changed.connect(self._on_button_mode)
        self.button_colors.colors_changed.connect(self._on_button_colors)

        self._update_slider_visibility()
        self._update_button_visibility()

    # ── Visibility Updaters ──────────────────────────────────────────────

    def _update_slider_visibility(self):
        has_fill = (self.slider_fill.get_value() != 0)
        self.lbl_s_style.setVisible(has_fill)
        self.slider_style.setVisible(has_fill)
        
        is_solid = (self.slider_style.get_value() == 1)
        self.lbl_s_mode.setVisible(has_fill and is_solid)
        self.slider_mode.setVisible(has_fill and is_solid)
        
        self.lbl_s_color.setVisible(has_fill and is_solid)
        self.slider_colors.setVisible(has_fill and is_solid)
        
        if has_fill and is_solid:
            self.slider_colors.set_mode(self.slider_mode.get_value() == 0)

    def _update_button_visibility(self):
        has_fill = (self.button_fill.get_value() != 0)
        self.lbl_b_style.setVisible(has_fill)
        self.button_style.setVisible(has_fill)
        
        is_solid = (self.button_style.get_value() == 1)
        self.lbl_b_mode.setVisible(has_fill and is_solid)
        self.button_mode.setVisible(has_fill and is_solid)
        
        self.lbl_b_color.setVisible(has_fill and is_solid)
        self.button_colors.setVisible(has_fill and is_solid)
        
        if has_fill and is_solid:
            self.button_colors.set_mode(self.button_mode.get_value() == 0)

    # ── Handlers ──────────────────────────────────────────────────────────

    def _on_brightness(self, value: int):
        settings_manager.set_led_brightness(value)
        if self._board_comm:
            self._board_comm.send_led_params(brightness=value)

    def _on_anim_speed(self, value: int):
        settings_manager.set_led_anim_speed(value)
        if self._board_comm:
            self._board_comm.send_led_params(anim_speed=value)

    def _on_slider_fill(self, fill: int):
        settings_manager.set_slider_led_fill(fill)
        self._update_slider_visibility()
        if self._board_comm:
            self._board_comm.send_led_params(slider_fill=fill)

    def _on_slider_style(self, style: int):
        settings_manager.set_slider_led_style(style)
        self._update_slider_visibility()
        if self._board_comm:
            self._board_comm.send_led_params(slider_style=style)

    def _on_slider_mode(self, mode_idx: int):
        mode_str = "all" if mode_idx == 0 else "per_slider"
        settings_manager.set_slider_color_mode(mode_str)
        self._update_slider_visibility()

    def _on_slider_colors(self, colors_list: list):
        settings_manager.set_slider_led_colors(colors_list)
        if self._board_comm:
            self._board_comm.send_led_params(slider_colors=colors_list)

    def _on_button_fill(self, fill: int):
        settings_manager.set_button_led_fill(fill)
        self._update_button_visibility()
        if self._board_comm:
            self._board_comm.send_led_params(button_fill=fill)

    def _on_button_style(self, style: int):
        settings_manager.set_button_led_style(style)
        self._update_button_visibility()
        if self._board_comm:
            self._board_comm.send_led_params(button_style=style)

    def _on_button_mode(self, mode_idx: int):
        mode_str = "all" if mode_idx == 0 else "per_button"
        settings_manager.set_button_color_mode(mode_str)
        self._update_button_visibility()

    def _on_button_colors(self, colors_list: list):
        settings_manager.set_button_led_colors(colors_list)
        if self._board_comm:
            self._board_comm.send_led_params(button_colors=colors_list)
