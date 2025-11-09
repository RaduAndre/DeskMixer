"""Button Section Handler - Business logic for button bindings"""
import os
from utils.error_handler import log_error


class ButtonSectionHandler:
    """Handles button bindings business logic"""

    def __init__(self, audio_manager, config_manager, ui_helpers, serial_handler=None):
        """
        Initialize button section handler

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
        self.device_button_count = 0
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
            self.device_button_count = button_count
            print(f"Device config: {button_count} buttons")

            if self.ui_callback:
                self.ui_callback('device_config', slider_count, button_count)

        except Exception as e:
            log_error(e, "Error handling device config")

    def get_required_buttons(self):
        """
        Get set of required buttons (from device and config)

        Returns:
            Tuple of (required_buttons, config_buttons, device_buttons)
        """
        config = self.config_manager.load_config()
        config_bindings = config.get('button_bindings', {})

        # Find which buttons exist in config
        config_buttons = set()
        for button_name in config_bindings.keys():
            if button_name.startswith('b') and button_name[1:].isdigit():
                config_buttons.add(int(button_name[1:]))

        # Union of device and config buttons
        device_buttons = set(range(1, self.device_button_count + 1))
        required_buttons = device_buttons.union(config_buttons)

        return required_buttons, config_buttons, device_buttons

    def load_button_bindings(self):
        """
        Load button bindings from config

        Returns:
            Dictionary of button bindings
        """
        config = self.config_manager.load_config()
        return config.get('button_bindings', {})

    def load_button_binding(self, button_name):
        """
        Load specific button binding

        Args:
            button_name: Button name (e.g., 'b1')

        Returns:
            Dictionary with binding data or empty dict
        """
        config = self.config_manager.load_config()
        button_bindings = config.get('button_bindings', {})
        binding_data = button_bindings.get(button_name, {})

        # Normalize to dict format
        if isinstance(binding_data, dict):
            return {
                'action': binding_data.get('action', ''),
                'target': binding_data.get('target', ''),
                'keybind': binding_data.get('keybind', ''),
                'app_path': binding_data.get('app_path', ''),
                'app_display_name': binding_data.get('app_display_name', ''),
                'output_mode': binding_data.get('output_mode', 'cycle'),
                'output_device': binding_data.get('output_device', '')
            }
        else:
            return {
                'action': binding_data,
                'target': '',
                'keybind': '',
                'app_path': '',
                'app_display_name': '',
                'output_mode': 'cycle',
                'output_device': ''
            }

    def save_button_binding(self, button_name, action, target='', keybind='',
                           app_path='', app_display_name='', output_mode='cycle',
                           output_device=''):
        """
        Save button binding

        Args:
            button_name: Button name (e.g., 'b1')
            action: Action to perform
            target: Target for action (optional)
            keybind: Keybind string (optional)
            app_path: App path for launch_app action (optional)
            app_display_name: Display name for app (optional)
            output_mode: Output mode for switch_audio_output (optional)
            output_device: Output device name (optional)
        """
        config = self.config_manager.load_config()

        if 'button_bindings' not in config:
            config['button_bindings'] = {}

        config['button_bindings'][button_name] = {
            'action': action,
            'target': target,
            'keybind': keybind,
            'app_path': app_path,
            'app_display_name': app_display_name,
            'output_mode': output_mode,
            'output_device': output_device
        }

        self.config_manager.save_config(config)

    def clear_button_binding(self, button_name):
        """
        Clear button binding

        Args:
            button_name: Button name (e.g., 'b1')
        """
        config = self.config_manager.load_config()

        if 'button_bindings' in config and button_name in config['button_bindings']:
            # Reset to default empty binding
            config['button_bindings'][button_name] = {
                'action': '',
                'target': '',
                'keybind': '',
                'app_path': '',
                'app_display_name': '',
                'output_mode': 'cycle',
                'output_device': ''
            }

            self.config_manager.save_config(config)

    def get_audio_output_devices(self):
        """
        Get list of available audio output devices

        Returns:
            List of device names
        """
        try:
            # Import here to avoid circular dependencies
            from pycaw.pycaw import AudioUtilities
            devices = AudioUtilities.GetAllDevices()
            device_names = []

            for device in devices:
                try:
                    # Get device friendly name
                    device_name = device.FriendlyName
                    if device_name:
                        device_names.append(device_name)
                except Exception:
                    continue

            return sorted(set(device_names))

        except Exception as e:
            log_error(e, "Error getting audio output devices")
            return []

    def validate_app_path(self, app_path):
        """
        Validate application path

        Args:
            app_path: Path to application

        Returns:
            True if valid, False otherwise
        """
        if not app_path:
            return False

        # Remove quotes if present
        app_path = app_path.strip('"').strip("'")

        # Check if file exists
        return os.path.exists(app_path.split()[0])

    def test_button_action(self, action, target='', keybind='', app_path='',
                          output_mode='cycle', output_device=''):
        """
        Test button action

        Args:
            action: Action to test
            target: Target for action
            keybind: Keybind string
            app_path: App path for launch_app
            output_mode: Output mode for switch_audio_output
            output_device: Output device name

        Returns:
            Tuple of (success, message)
        """
        try:
            from utils.actions import ActionHandler
            action_handler = ActionHandler(self.audio_manager)

            # Build kwargs
            kwargs = {}
            if target:
                kwargs['target'] = target
            if keybind:
                kwargs['keys'] = keybind
            if app_path:
                kwargs['app_path'] = app_path
            if output_mode:
                kwargs['output_mode'] = output_mode
            if output_device:
                kwargs['device_name'] = output_device

            # Execute action
            action_handler.execute_action(action, **kwargs)

            return True, f"Action '{action}' executed successfully"

        except Exception as e:
            error_msg = f"Error testing action '{action}': {str(e)}"
            log_error(e, error_msg)
            return False, error_msg

    def get_available_actions(self):
        """Get list of available actions"""
        return self.helpers.get_available_actions()

    def get_available_targets(self):
        """Get list of available binding targets"""
        return self.helpers.get_available_targets()

    def normalize_action_name(self, display_name):
        """Convert action display name to internal name"""
        return self.helpers.normalize_action_name(display_name)

    def normalize_target_name(self, display_name):
        """Convert target display name to internal name"""
        return self.helpers.normalize_target_name(display_name)

    def get_action_display_name(self, internal_name):
        """Convert internal action name to display name"""
        return self.helpers.get_action_display_name(internal_name)

    def get_target_display_name(self, internal_name):
        """Convert internal target name to display name"""
        return self.helpers.get_display_name(internal_name)
