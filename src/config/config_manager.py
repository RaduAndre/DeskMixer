import json
import os
import sys
from utils.error_handler import log_error


def get_app_data_folder():
    """Get the application data folder in user's Documents"""
    documents_path = os.path.join(os.path.expanduser('~'), 'Documents')
    app_folder = os.path.join(documents_path, 'DeskMixer')
    os.makedirs(app_folder, exist_ok=True)
    return app_folder


class ConfigManager:
    """
    Manage configuration settings.
    Singleton pattern to ensure global access to the same state.
    """
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_file="config.json"):
        if self._initialized:
            return
            
        self.config_file = config_file

        # Use Documents/DeskMixer folder for configuration
        self.config_dir = get_app_data_folder()
        self.config_path = os.path.join(self.config_dir, self.config_file)

        self.config = {}
        self.has_changes = False

        # Create config directory if it doesn't exist
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

        # Load configuration on initialization
        self.load_config()
        self._initialized = True

    def load_config(self):
        """Load configuration from file"""
        self.load_failed = False
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {}
        except Exception as e:
            log_error(e, f"Error loading configuration from {self.config_path}")
            self.load_failed = True
            self.config = {}
            
            # Backup corrupted file
            try:
                import shutil
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{self.config_path}.corrupted_{timestamp}.json"
                shutil.copy2(self.config_path, backup_path)
                print(f"Backed up corrupted config to {backup_path}")
            except Exception as backup_error:
                log_error(backup_error, "Failed to backup corrupted config")
                
        return self.config

    def save_config(self):
        """Save configuration to file using atomic write to prevent corruption"""
        try:
            # Ensure the config directory exists
            os.makedirs(self.config_dir, exist_ok=True)

            # Atomic Save: Write to temp file first, then rename
            temp_path = self.config_path + ".tmp"
            
            with open(temp_path, 'w') as f:
                json.dump(self.config, f, indent=4, sort_keys=True)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    # fsync can fail on some filesystems, usually safe to ignore if flush worked
                    pass
            
            # Atomic replacement
            try:
                os.replace(temp_path, self.config_path)
            except (PermissionError, OSError):
                # Fallback for Windows if replace fails due to locking
                # Try remove + rename
                if os.path.exists(self.config_path):
                    os.remove(self.config_path)
                os.rename(temp_path, self.config_path)

            return True
        except Exception as e:
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            log_error(e, f"Error saving configuration to {self.config_path}")
            return False

    def add_binding(self, var_name, app_names):
        """Add or update a variable binding (supports single app or list of apps)"""
        try:
            if not var_name or not var_name.startswith('s'):
                return False

            if 'variable_bindings' not in self.config:
                self.config['variable_bindings'] = {}

            # Normalize input to list
            if isinstance(app_names, str):
                app_names = [app_names] if app_names else []
            elif not isinstance(app_names, list):
                app_names = []

            # Filter out empty values but keep "None" if strictly intended? 
            # Actually user wants "None" to result in the null object.
            
            # Check for explicit "None" or empty
            is_none = False
            if not app_names:
                is_none = True
            elif len(app_names) == 1 and (app_names[0] == "None" or app_names[0] is None):
                is_none = True
            
            if is_none:
                # User requested specific format for None
                app_names = [{"value": None, "argument": None}]
            else:
                 # Filter valid apps
                 app_names = [app for app in app_names if app and app != "None"]
                 if not app_names:
                     app_names = [{"value": None, "argument": None}]

            # Check if binding actually changed
            current = self.config['variable_bindings'].get(var_name)

            # Normalize current for comparison
            # Current might be legacy list of strings OR new list of dicts
            current_apps = []
            if isinstance(current, dict):
                # Legacy special structure? Or just dict access
                # If it's the new style, it's simple list of dicts stored directly
                # If it's old style dict with 'app_name' key?
                current_apps = current.get('app_name', [])
                if isinstance(current_apps, str):
                    current_apps = [current_apps]
            elif isinstance(current, list):
                current_apps = current
            elif isinstance(current, str):
                current_apps = [current]
            
            # Comparison Logic
            changed = False
            try:
                # Try set comparison (for strings/numbers) - ignores order
                if set(current_apps) != set(app_names):
                    changed = True
            except TypeError:
                # Fallback for unhashable types (e.g. dicts) - sensitive to order
                # Use simple equality for lists of dicts
                if current_apps != app_names:
                    changed = True

            if changed:
                self.config['variable_bindings'][var_name] = app_names
                self.has_changes = True
                self.save_config()
                return True

            return False

        except Exception as e:
            log_error(e, f"Error adding binding for {var_name}")
            return False

    def remove_binding(self, var_name):
        """Remove a variable binding"""
        try:
            if 'variable_bindings' in self.config and var_name in self.config['variable_bindings']:
                del self.config['variable_bindings'][var_name]
                self.save_config()
                return True
            return False
        except Exception as e:
            log_error(e, f"Error removing binding for {var_name}")
            return False

    def add_button_binding(self, button_name, binding_data):
        """Add or update a button binding"""
        try:
            if not button_name or not button_name.startswith('b'):
                return False

            if 'button_bindings' not in self.config:
                self.config['button_bindings'] = {}

            current = self.config['button_bindings'].get(button_name, {})
            if current != binding_data:
                self.config['button_bindings'][button_name] = binding_data
                self.has_changes = True
                self.save_config()
                return True

            return False

        except Exception as e:
            log_error(e, f"Error adding button binding for {button_name}")
            return False

    def remove_button_binding(self, button_name):
        """Remove a button binding"""
        if 'button_bindings' in self.config and button_name in self.config['button_bindings']:
            del self.config['button_bindings'][button_name]
            self.has_changes = True

    def set_last_connected_port(self, port):
        """Set the last connected serial port (baud rate is fixed at 115200)"""
        if self.config.get('last_connected_port') != port:
            self.config['last_connected_port'] = port
            self.has_changes = True

    def set_slider_sampling(self, mode):
        """Set the global volume control mode for all bindings"""
        valid_modes = ['instant', 'responsive', 'soft', 'normal', 'hard']
        mode = mode.lower() if mode else 'normal'

        if mode not in valid_modes:
            mode = 'normal'

        if self.config.get('slider_sampling') != mode:
            self.config['slider_sampling'] = mode
            self.has_changes = True
            self.save_config()
            return True
        return False

    def get_slider_sampling(self, default='normal'):
        """Get the global volume control mode"""
        return self.config.get('slider_sampling', default)

    def get_app_list(self):
        """Get the list of user's preferred apps"""
        return self.config.get('app_list', [])

    def add_to_app_list(self, app_name):
        """Add an app to the user's preferred app list"""
        try:
            if not app_name or app_name in ["None", "⌀ None"]:
                return False

            if 'app_list' not in self.config:
                self.config['app_list'] = []

            # Add if not already in list
            if app_name not in self.config['app_list']:
                self.config['app_list'].append(app_name)
                self.has_changes = True
                self.save_config()
                return True

            return False
        except Exception as e:
            log_error(e, f"Error adding {app_name} to app list")
            return False

    def remove_from_app_list(self, app_name):
        """Remove an app from the user's preferred app list"""
        try:
            if 'app_list' in self.config and app_name in self.config['app_list']:
                self.config['app_list'].remove(app_name)
                self.has_changes = True
                self.save_config()
                return True
            return False
        except Exception as e:
            log_error(e, f"Error removing {app_name} from app list")
            return False

    def set_start_in_tray(self, value):
        """Set the value for the start_in_tray config key."""
        key = 'start_in_tray'
        new_value = bool(value)
        if self.config.get(key) != new_value:
            self.config[key] = new_value
            self.has_changes = True

    def get_start_in_tray(self, default=False):
        """Get the value for the start_in_tray config key."""
        return self.config.get('start_in_tray', default)

    def save_config_if_changed(self):
        """Save configuration only if there are changes"""
        if self.has_changes:
            self.save_config()
            self.has_changes = False
            return True
        return False

    def get_config_value(self, key, default=None):
        """Get a configuration value"""
        return self.config.get(key, default)

    def load_variable_binding(self, var_name):
        """Load a specific variable binding"""
        try:
            if not self.config:
                self.load_config()

            bindings = self.config.get('variable_bindings', {})
            binding = bindings.get(var_name)

            if binding:
                # Handle multiple formats: string, list, or dict
                if isinstance(binding, dict):
                    app_names = binding.get('app_name', [])
                    if isinstance(app_names, str):
                        return [app_names]
                    return app_names
                elif isinstance(binding, list):
                    return binding
                else:
                    return [binding] if binding else []
            return None

        except Exception as e:
            log_error(e, "Error loading variable binding")
            return None
    
    def set_screen_active(self, value):
        """Set the screen_active state (0 or 1)."""
        new_value = int(value) if value in [0, 1] else 0
        if self.config.get('screen_active') != new_value:
            self.config['screen_active'] = new_value
            self.has_changes = True
            self.save_config()
            return True
        return False
    
    def get_screen_active(self, default=0):
        """Get the screen_active state."""
        return self.config.get('screen_active', default)