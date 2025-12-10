"""UI Helper functions for configuration"""
from utils.error_handler import log_error


class UIHelpers:
    """Utility methods for UI configuration"""

    def __init__(self, audio_manager, config_manager):
        """
        Initialize UI helpers

        Args:
            audio_manager: Audio manager instance
            config_manager: Config manager instance
        """
        self.audio_manager = audio_manager
        self.config_manager = config_manager

    def get_available_actions(self):
        """Get list of available actions"""
        return [
            "Play/Pause",
            "Next Track",
            "Previous Track",
            "Seek Forward",
            "Seek Backward",
            "Volume Up",
            "Volume Down",
            "Mute",
            "Switch Audio Output",
            "Keybind (Custom)",
            "Launch App"
        ]

    def normalize_action_name(self, display_name):
        """
        Convert display name to internal action name

        Args:
            display_name: Display name (e.g., "Play/Pause")

        Returns:
            Internal action name (e.g., "play_pause")
        """
        action_map = {
            "Play/Pause": "play_pause",
            "Next Track": "next_track",
            "Previous Track": "previous_track",
            "Seek Forward": "seek_forward",
            "Seek Backward": "seek_backward",
            "Volume Up": "volume_up",
            "Volume Down": "volume_down",
            "Mute": "mute",
            "Switch Audio Output": "switch_audio_output",
            "Keybind (Custom)": "keybind",
            "Launch App": "launch_app"
        }
        return action_map.get(display_name.strip(), display_name)

    def get_action_display_name(self, internal_name):
        """
        Convert internal name to display name

        Args:
            internal_name: Internal action name (e.g., "play_pause")

        Returns:
            Display name (e.g., "Play/Pause")
        """
        display_map = {
            "play_pause": "Play/Pause",
            "play": "Play",
            "pause": "Pause",
            "next_track": "Next Track",
            "previous_track": "Previous Track",
            "seek_forward": "Seek Forward",
            "seek_backward": "Seek Backward",
            "volume_up": "Volume Up",
            "volume_down": "Volume Down",
            "mute": "Mute",
            "switch_audio_output": "Switch Audio Output",
            "keybind": "Keybind (Custom)",
            "launch_app": "Launch App"
        }
        return display_map.get(internal_name, internal_name)

    def get_available_targets(self):
        """Get list of available binding targets"""
        try:
            targets = [
                "Master",
                "Microphone",
                "System Sounds",
                "Current Application",
                "Unbound",
                "None"
            ]

            targets.append("─" * 30)

            apps = self.audio_manager.get_all_audio_apps()

            if apps:
                for app_name in sorted(apps.keys()):
                    targets.append(f"{app_name}")
            else:
                targets.append("(No audio apps running)")

            return targets

        except Exception as e:
            log_error(e, "Error getting available targets")
            return ["Master", "Microphone", "System Sounds",
                    "Current Application", "Unbound", "None"]

    def normalize_target_name(self, display_name):
        """
        Convert display name to internal name

        Args:
            display_name: Display name (e.g., "Master")

        Returns:
            Internal target name (e.g., "Master")
        """
        if not display_name:
            return ""

        name = display_name.strip()
        
        # Handle separator/placeholder
        if name.startswith("─") or name.startswith("("):
            return ""

        return name

    def get_display_name(self, internal_name):
        """
        Convert internal name to display name

        Args:
            internal_name: Internal target name (e.g., "Master")

        Returns:
            Display name (e.g., "Master")
        """
        if not internal_name:
            return ""

        return internal_name.strip()

    def check_duplicate_binding(self, var_name, app_name):
        """
        Check if a variable binding already exists for the app

        Args:
            var_name: Variable name to exclude from check
            app_name: App name to check for duplicates

        Returns:
            True if duplicate binding exists, False otherwise
        """
        try:
            # Special targets that can be bound multiple times
            special_targets = ["Master", "Microphone", "System Sounds",
                             "Current Application", "Unbound", "None"]

            if not app_name or app_name in special_targets:
                return False

            config = self.config_manager.load_config()
            bindings = config.get('variable_bindings', {})

            for name, details in bindings.items():
                if name != var_name:  # Don't check against self
                    # Handle multiple formats
                    if isinstance(details, dict):
                        bound_apps = details.get('app_name', [])
                    elif isinstance(details, list):
                        bound_apps = details
                    else:
                        bound_apps = [details] if details else []

                    if isinstance(bound_apps, str):
                        bound_apps = [bound_apps]

                    if app_name in bound_apps:
                        return True

            return False

        except Exception as e:
            log_error(e, "Error checking duplicate binding")
            return False
