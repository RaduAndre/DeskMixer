"""
Font configuration for DeskMixer UI.
Provides QFont objects and stylesheet generators for consistent typography.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtGui import QFont
from ui2 import colors

# Font family
FONT_FAMILY = "Montserrat"
FALLBACK_FONT = "Segoe UI"

def get_font(size: int, bold: bool = False) -> QFont:
    """Create a QFont with the specified size and weight."""
    font = QFont(FONT_FAMILY)
    font.setPixelSize(size)
    if bold:
        font.setBold(True)
    return font

# Font presets
def slider_name_font() -> QFont:
    """Montserrat Bold 12px for slider names."""
    return get_font(12, bold=True)

def button_name_font() -> QFont:
    """Montserrat Bold 14px for button names."""
    return get_font(14, bold=True)

def menu_name_font() -> QFont:
    """Montserrat Bold 18px for menu titles."""
    return get_font(18, bold=True)

def menu_element_font(bold: bool = False) -> QFont:
    """Montserrat Regular/Bold 14px for menu elements."""
    return get_font(14, bold=bold)

# Stylesheet generators
def slider_name_style() -> str:
    """Stylesheet for slider name labels."""
    return f"""
        color: {colors.WHITE};
        font-family: {FONT_FAMILY}, {FALLBACK_FONT};
        font-size: 12px;
        font-weight: bold;
    """

def button_name_style(active: bool = False) -> str:
    """Stylesheet for button name labels."""
    color = colors.BLACK if active else colors.WHITE
    return f"""
        color: {color};
        font-family: {FONT_FAMILY}, {FALLBACK_FONT};
        font-size: 14px;
        font-weight: bold;
    """

def menu_name_style() -> str:
    """Stylesheet for menu title labels."""
    return f"""
        color: {colors.WHITE};
        font-family: {FONT_FAMILY}, {FALLBACK_FONT};
        font-size: 18px;
        font-weight: bold;
    """

def menu_element_style(active: bool = False) -> str:
    """Stylesheet for menu element labels."""
    color = colors.BLACK if active else colors.WHITE
    weight = "bold" if active else "normal"
    return f"""
        color: {color};
        font-family: {FONT_FAMILY}, {FALLBACK_FONT};
        font-size: 14px;
        font-weight: {weight};
    """
