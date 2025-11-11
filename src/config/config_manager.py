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
    """Manage configuration settings"""

    def __init__(self, config_file="config.json"):
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

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
            else:
                self.config = {}
        except Exception as e:
            log_error(e, f"Error loading configuration from {self.config_path}")
            self.config = {}
        return self.config

    def save_config(self):
        """Save configuration to file"""
        try:
            # Ensure the config directory exists
            os.makedirs(self.config_dir, exist_ok=True)

            # Save with proper formatting
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4, sort_keys=True)

            return True
        except Exception as e:
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

            # Filter out empty values
            app_names = [app for app in app_names if app]

            # Default to Master if empty
            if not app_names:
                app_names = ['Master']

            # Check if binding actually changed
            current = self.config['variable_bindings'].get(var_name)

            # Normalize current for comparison
            if isinstance(current, dict):
                current_apps = current.get('app_name', [])
                if isinstance(current_apps, str):
                    current_apps = [current_apps]
            elif isinstance(current, list):
                current_apps = current
            elif isinstance(current, str):
                current_apps = [current]
            else:
                current_apps = []

            if set(current_apps) != set(app_names):
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

    def set_last_connected_port(self, port, baud):
        """Set the last connected serial port"""
        if (self.config.get('last_connected_port') != port or
                self.config.get('last_connected_baud') != str(baud)):
            self.config['last_connected_port'] = port
            self.config['last_connected_baud'] = str(baud)
            self.has_changes = True

    def set_slider_sampling(self, mode):
        """Set the global volume control mode for all bindings"""
        valid_modes = ['soft', 'normal', 'hard']
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