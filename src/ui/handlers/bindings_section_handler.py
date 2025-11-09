"""Bindings Section Handler - Business logic for slider bindings"""
from utils.error_handler import log_error


class BindingsSectionHandler:
    """Handles slider bindings business logic"""

    def __init__(self, audio_manager, config_manager, ui_helpers, serial_handler=None):
        """
        Initialize bindings section handler

        Args:
            audio_manager: Audio manager instance
            config_manager: Config manager instance
            ui_helpers: UI helpers instance
            serial_handler: Optional serial handler for device config
        """
        self.audio_manager = audio_manager
        self.config_manager = config_manager
        self.helpers = ui_helpers
        self.serial_handler = serial_handler
        self.device_slider_count = 0
        self.ui_callback = None

    def set_ui_callback(self, callback):
        """Set callback for UI updates"""
        self.ui_callback = callback

    def register_device_config_callback(self):
        """Register for device configuration updates"""
        if self.serial_handler:
            self.serial_handler.add_config_callback(self._on_device_config)

    def _on_device_config(self, slider_count, button_count):
        """
        Handle device configuration updates

        Args:
            slider_count: Number of sliders on device
            button_count: Number of buttons on device
        """
        try:
            self.device_slider_count = slider_count
            print(f"Device config: {slider_count} sliders")

            if self.ui_callback:
                self.ui_callback('device_config', slider_count, button_count)

        except Exception as e:
            log_error(e, "Error handling device config")

    def get_slider_sampling(self):
        """Get current slider sampling mode"""
        return self.config_manager.get_slider_sampling()

    def set_slider_sampling(self, mode):
        """
        Set slider sampling mode

        Args:
            mode: Sampling mode (soft, normal, hard)
        """
        self.config_manager.set_slider_sampling(mode)
        self.config_manager.save_config_if_changed()

    def load_variable_bindings(self):
        """
        Load variable bindings from config

        Returns:
            Dictionary of variable bindings
        """
        config = self.config_manager.load_config()
        return config.get('variable_bindings', {})

    def load_variable_binding(self, var_name):
        """
        Load specific variable binding

        Args:
            var_name: Variable name (e.g., 's1')

        Returns:
            List of app names or None
        """
        return self.config_manager.load_variable_binding(var_name)

    def save_variable_binding(self, var_name, app_names):
        """
        Save variable binding

        Args:
            var_name: Variable name (e.g., 's1')
            app_names: List of app names to bind
        """
        self.config_manager.save_variable_binding(var_name, app_names)

    def get_required_sliders(self):
        """
        Get set of required sliders (from device and config)

        Returns:
            Set of slider numbers
        """
        config = self.config_manager.load_config()
        config_bindings = config.get('variable_bindings', {})

        # Find which sliders exist in config
        config_sliders = set()
        for var_name in config_bindings.keys():
            if var_name.startswith('s') and var_name[1:].isdigit():
                config_sliders.add(int(var_name[1:]))

        # Union of device and config sliders
        device_sliders = set(range(1, self.device_slider_count + 1))
        required_sliders = device_sliders.union(config_sliders)

        return required_sliders, config_sliders, device_sliders

    def check_duplicate_binding(self, var_name, app_name):
        """
        Check if app is already bound to another variable

        Args:
            var_name: Variable name to exclude from check
            app_name: App name to check

        Returns:
            True if duplicate exists
        """
        return self.helpers.check_duplicate_binding(var_name, app_name)

    def get_available_targets(self):
        """Get list of available binding targets"""
        return self.helpers.get_available_targets()

    def normalize_target_name(self, display_name):
        """Convert display name to internal name"""
        return self.helpers.normalize_target_name(display_name)

    def get_display_name(self, internal_name):
        """Convert internal name to display name"""
        return self.helpers.get_display_name(internal_name)
