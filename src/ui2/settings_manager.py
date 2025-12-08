"""
Settings manager for holding application state.
"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.deskmixer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

class SettingsManager:
    """
    Manages application settings and state.
    Singleton pattern to ensure global access to the same state.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize default settings."""
        self.start_hidden = 0
        self.start_on_startup = 0
        self.button_alignment = "horizontal"  # "vertical" or "horizontal"
        self.button_alignment = "horizontal"  # "vertical" or "horizontal" - Deprecated but kept for compatibility?
        self.slider_sampling = "normal" # "soft", "normal", "hard"
        
        # Grid Layout Settings
        self.grid_rows = 0 # 0 means auto or unset
        self.grid_cols = 0 # 0 means auto or unset
        self.button_matrix = [] # List of lists of button IDs
        self.slider_order = [] # List of slider IDs
        
        # Load from disk
        self.load()

    def load(self):
        """Load settings from memory (defaults)."""
        # User requested variable-only storage (no file persistence)
        # We rely on defaults initialized in _initialize
        pass

    def save(self):
        """Save settings to memory (no-op for file)."""
        # No disk usage
        pass
        
    def get_start_hidden(self) -> int:
        return self.start_hidden
    
    def set_start_hidden(self, value: int):
        self.start_hidden = value
        self.save()
        
    def get_start_on_startup(self) -> int:
        return self.start_on_startup
        
    def set_start_on_startup(self, value: int):
        self.start_on_startup = value
        self.save()
        
    def get_button_alignment(self) -> str:
        return self.button_alignment
        
    def set_button_alignment(self, value: str):
        if value in ["vertical", "horizontal"]:
            self.button_alignment = value
            self.save()

    def get_slider_sampling(self) -> str:
        return self.slider_sampling
        
    def set_slider_sampling(self, value: str):
        if value in ["soft", "normal", "hard"]:
            self.slider_sampling = value
            self.save()

    # Grid Layout Methods
    def get_grid_dimensions(self) -> tuple[int, int]:
        return self.grid_rows, self.grid_cols
        
    def set_grid_dimensions(self, rows: int, cols: int):
        self.grid_rows = rows
        self.grid_cols = cols
        self.save()
        
    def get_button_matrix(self):
        return self.button_matrix
        
    def set_button_matrix(self, matrix):
        self.button_matrix = matrix
        self.save()
        
    def get_slider_order(self):
        return self.slider_order
        
    def set_slider_order(self, order):
        self.slider_order = order
        self.save()

# Global instance
settings_manager = SettingsManager()
