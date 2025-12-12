"""
Icon manager for loading and caching SVG icons.
"""

import os
from PySide6.QtGui import QIcon
from typing import Dict

class IconManager:
    """Manages loading and caching of SVG icons."""
    
    _instance = None
    _icon_cache: Dict[str, QIcon] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Get the icon directory path
        # ui2 is in src/ui2, icons are in src/icons/ui
        # So we go up one level from ui2 to src, then to icons/ui
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_dir = os.path.abspath(os.path.join(current_dir, "..", "icons", "ui"))
    
    def get_icon(self, name: str) -> QIcon:
        """
        Get an icon by name. The icon is cached after first load.
        
        Args:
            name: Icon filename (e.g., 'settings.svg')
        
        Returns:
            QIcon object
        """
        if name not in self._icon_cache:
            icon_path = os.path.join(self.icon_dir, name)
            if os.path.exists(icon_path):
                self._icon_cache[name] = QIcon(icon_path)
            else:
                # Return empty icon if file not found
                print(f"Warning: Icon not found: {icon_path}")
                self._icon_cache[name] = QIcon()
        
        return self._icon_cache[name]
    
    
    def get_active_icon(self, base_name: str) -> QIcon:
        """
        Get the active variant of an icon.
        Converts 'name.svg' to 'name_active.svg'.
        
        Args:
            base_name: Base icon filename (e.g., 'mute.svg')
        
        Returns:
            QIcon object for the active variant
        """
        if base_name.endswith('.svg'):
            active_name = base_name.replace('.svg', '_active.svg')
        else:
            active_name = f"{base_name}_active"
        
        return self.get_icon(active_name)
    
    def get_icon_path(self, name: str) -> str:
        """
        Get the full path to an icon file.
        
        Args:
            name: Icon filename
        
        Returns:
            Full path to icon file
        """
        return os.path.join(self.icon_dir, name)
    
    def get_colored_icon(self, name: str, color_hex: str) -> QIcon:
        """
        Get an icon dynamically colored with specific color.
        
        Args:
            name: Icon filename (e.g. 'settings.svg')
            color_hex: Color hex string (e.g. '#FFFFFF')
        
        Returns:
            QIcon object
        """
        from PySide6.QtGui import QPixmap, QPainter, QColor
        from PySide6.QtCore import Qt
        
        # Check cache if needed - for now minimal caching or rely on get_icon caching basics
        # Caching combined (name, color) might be good optimization
        cache_key = f"{name}_{color_hex}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        # Load base icon
        base_icon = self.get_icon(name)
        
        # Create pixmap from icon
        pixmap = base_icon.pixmap(32, 32) # Standard size buffer
        
        if pixmap.isNull():
             return QIcon()
             
        # Create a new pixmap to hold colored version
        colored_pixmap = QPixmap(pixmap.size())
        colored_pixmap.fill(Qt.transparent)
        
        painter = QPainter(colored_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Fill with target color
        painter.setBrush(QColor(color_hex))
        painter.setPen(Qt.NoPen)
        painter.drawRect(colored_pixmap.rect())
        
        # 2. Draw original icon using DestinationIn mode
        # This keeps the color only where the icon is opaque
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.drawPixmap(0, 0, pixmap)
        
        painter.end()
        
        # Cache and return
        icon = QIcon(colored_pixmap)
        self._icon_cache[cache_key] = icon
        return icon

    # Action to Icon Mapping
    ACTION_ICONS = {
        "Play/Pause": "play_pause.svg",
        "Previous": "previous.svg",
        "Next": "next.svg",
        "Volume Up": "volume_up.svg",
        "Volume Down": "volume_down.svg",
        "Seek Backward": "seek_backward.svg",
        "Seek Forward": "seek_forward.svg",
        "Mute": "mute.svg",
        "Switch Audio Output": "switch_output.svg",
        "Keybind": "keybind.svg",
        "Launch app": "open_app.svg",
        "None": "ghost.svg"
    }

    def get_action_icon_name(self, action: str) -> str:
        """Helper to get icon name for an action."""
        return self.ACTION_ICONS.get(action, "ghost.svg")


# Global instance
icon_manager = IconManager()
