import os
import sys

# Add project root to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.config_manager import ConfigManager

class SettingsManager:
    """
    Manages application settings and state using ConfigManager as backend.
    Singleton pattern to ensure global access to the same state.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize connection to ConfigManager."""
        self.config_manager = ConfigManager()
        
        # Ensure default values exist in ConfigManager if strictly needed,
        # but ConfigManager usually handles defaults via getters.
        pass

    def load(self):
        """Reload settings from backend."""
        self.config_manager.load_config()

    def save(self):
        """Save settings to backend."""
        self.config_manager.save_config_if_changed()
        
    def get_start_hidden(self) -> int:
        return 1 if self.config_manager.get_start_in_tray() else 0
    
    def set_start_hidden(self, value: int):
        self.config_manager.set_start_in_tray(bool(value))
        self.save()
        
    def get_start_on_startup(self) -> int:
        # This might be checked dynamically elsewhere, but if stored in config:
        return self.config_manager.get_config_value('start_on_startup', 0)
        
    def set_start_on_startup(self, value: int):
        # ConfigManager doesn't seem to have a setter for this exposed easily besides generic
        # but CoreController handles the actual startup registry change.
        # We just store the preference here if needed.
        # Assuming we store it in config for UI state:
        self.config_manager.config['start_on_startup'] = value
        self.config_manager.has_changes = True
        self.save()
        
    def get_button_alignment(self) -> str:
        return self.config_manager.get_config_value('ui2_button_alignment', 'horizontal')
        
    def set_button_alignment(self, value: str):
        if value in ["vertical", "horizontal"]:
            self.config_manager.config['ui2_button_alignment'] = value
            self.config_manager.has_changes = True
            self.save()

    def get_slider_sampling(self) -> str:
        return self.config_manager.get_slider_sampling()
        
    def set_slider_sampling(self, value: str):
        self.config_manager.set_slider_sampling(value)
        # set_slider_sampling already saves if changed
        
    # Grid Layout Methods
    def get_grid_dimensions(self) -> tuple[int, int]:
        rows = self.config_manager.get_config_value('ui2_grid_rows', 0)
        cols = self.config_manager.get_config_value('ui2_grid_cols', 0)
        return rows, cols
        
    def set_grid_dimensions(self, rows: int, cols: int):
        self.config_manager.config['ui2_grid_rows'] = rows
        self.config_manager.config['ui2_grid_cols'] = cols
        self.config_manager.has_changes = True
        self.save()
        
    def get_button_matrix(self):
        return self.config_manager.get_config_value('ui2_button_matrix', [])
        
    def set_button_matrix(self, matrix):
        self.config_manager.config['ui2_button_matrix'] = matrix
        self.config_manager.has_changes = True
        self.save()
        
    def get_slider_order(self):
        return self.config_manager.get_config_value('ui2_slider_order', [])
        
    def set_slider_order(self, order):
        self.config_manager.config['ui2_slider_order'] = order
        self.config_manager.has_changes = True
        self.save()

    # --- New Methods for Positional Mapping (Index-based) ---

    def get_slider_binding_at_index(self, index: int) -> list[str]:
        """Get bindings for a slider at specific physical index (pos 0 = s1)."""
        key = f"s{index + 1}"
        return self.config_manager.load_variable_binding(key) or []
        
    def save_slider_binding_at_index(self, index: int, bindings: list[str]):
        """Save bindings for a slider at specific physical index."""
        key = f"s{index + 1}"
        self.config_manager.add_binding(key, bindings)

    def get_button_binding_at_index(self, index: int):
        """Get bindings for a button at specific physical index (pos 0 = b1)."""
        key = f"b{index + 1}"
        return self.config_manager.config.get('button_bindings', {}).get(key)

    def save_button_binding_at_index(self, index: int, binding_data: dict):
         """Save binding data for a button at specific physical index."""
         key = f"b{index + 1}"
         self.config_manager.add_button_binding(key, binding_data)

    # --- Deprecated / Helper ID methods (Still used for finding Order) ---

    def get_slider_id_from_index(self, index: int) -> str:
        """Map generic index to slider ID, e.g. 0 -> slider_0."""
        return f"slider_{index}"
        
    def get_config_key_from_slider_id(self, slider_id: str) -> str:
        """Deprecated: ID to key mapping is unreliable after reorder."""
        try:
            idx = int(slider_id.split('_')[1])
            return f"s{idx + 1}"
        except:
            return "s1"
            
    def get_slider_bindings(self, slider_id: str) -> list[str]:
        """Deprecated: Use get_slider_binding_at_index."""
        # Fallback to ID-based for backward compat if needed during migration
        key = self.get_config_key_from_slider_id(slider_id)
        return self.config_manager.load_variable_binding(key) or []
        
    def set_slider_bindings(self, slider_id: str, bindings: list[str]):
        """Deprecated."""
        key = self.get_config_key_from_slider_id(slider_id)
        self.config_manager.add_binding(key, bindings) 

    def get_button_bindings(self, button_id: str):
        """Deprecated: Use get_button_binding_at_index."""
        try:
             idx = int(button_id.split('_')[1])
             key = f"b{idx + 1}"
             return self.config_manager.config.get('button_bindings', {}).get(key)
        except:
            return None

    def set_button_binding(self, button_id: str, binding_data: dict):
         """Deprecated."""
         try:
             idx = int(button_id.split('_')[1])
             key = f"b{idx + 1}"
             self.config_manager.add_button_binding(key, binding_data)
         except:
             pass

    def get_app_list(self) -> list[str]:
        """Get the list of custom applications."""
        return self.config_manager.get_config_value('app_list', [])

    def add_app_to_list(self, app_name: str):
        """Add an application to the custom list."""
        current_list = self.get_app_list()
        # Case-insensitive check
        if not any(app.lower() == app_name.lower() for app in current_list):
            current_list.append(app_name)
            self.config_manager.config['app_list'] = current_list
            self.config_manager.has_changes = True
            self.save()

    def remove_app_from_list(self, app_name: str):
        """Remove an application from the custom list."""
        current_list = self.get_app_list()
        if app_name in current_list:
            current_list.remove(app_name)
            self.config_manager.config['app_list'] = current_list
            self.config_manager.has_changes = True
            self.save()

# Global instance
settings_manager = SettingsManager()
