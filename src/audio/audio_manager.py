from utils.error_handler import log_error
import atexit

# Import Driver
from audio.windows_audio import WindowsAudioDriver
from serial_comm.serial_controller import SerialController

# Try importing heavy audio libs; allow app to run without them (degraded mode).
AUDIO_AVAILABLE = True
try:
    # Check if we can import the driver dependencies
    import comtypes
    import pycaw
except ImportError:
    AUDIO_AVAILABLE = False

class AudioManager:
    """Manages all audio-related operations using platform-specific drivers"""

    def __init__(self):
        self.driver = None
        self.serial_handler = None
        self.config_manager = None
        self.window_monitor = None
        self.last_focused_app = None
        self.serial_controller = None
        
        # Track slider history for averaging - PER SLIDER
        # (Kept for compatibility if anything else uses it, but logic moved to controller)
        self.slider_history = {} 

        if AUDIO_AVAILABLE:
            self._initialize_driver()
            # Register cleanup on exit
            atexit.register(self.cleanup)
        else:
            log_error(Exception("Audio libs missing"), "AudioManager initialized in degraded mode")

    def _initialize_driver(self):
        """Initialize the appropriate audio driver"""
        try:
            # Currently only Windows is supported, but logic can be extended
            self.driver = WindowsAudioDriver()
            self.driver.initialize()
        except Exception as e:
            log_error(e, "Failed to initialize audio driver")
            raise RuntimeError("Audio driver initialization failed")

    def set_handlers(self, serial_handler, config_manager):
        self.serial_handler = serial_handler
        self.config_manager = config_manager
        
        # Initialize SerialController now that we have handlers
        if self.serial_handler and self.config_manager:
            self.serial_controller = SerialController(self, self.serial_handler, self.config_manager)
            self.serial_controller.start()

    # Delegate methods to driver
    def set_master_volume(self, level):
        if self.driver: self.driver.set_master_volume(level)

    def set_mic_volume(self, level):
        if self.driver: self.driver.set_mic_volume(level)

    def set_system_sounds_volume(self, level):
        if self.driver: self.driver.set_system_sounds_volume(level)

    def set_app_volume(self, app_name, level):
        if self.driver: self.driver.set_app_volume(app_name, level)

    def toggle_master_mute(self):
        if self.driver: self.driver.toggle_master_mute()

    def toggle_mic_mute(self):
        if self.driver: self.driver.toggle_mic_mute()

    def toggle_app_mute(self, app_name):
        if self.driver: self.driver.toggle_app_mute(app_name)

    def toggle_system_sounds_mute(self):
        if self.driver: self.driver.toggle_system_sounds_mute()

    def toggle_current_app_mute(self):
        """Toggle mute for the currently focused application"""
        if not self.driver: return
        
        focused_app = self.driver.get_focused_app()
        if focused_app:
            self.driver.toggle_app_mute(focused_app)
            
    def toggle_unbinded_mute(self):
        """
        Smart toggle for unbinded apps:
        - If ANY unbinded app is unmuted -> Mute ALL unbinded apps
        - If ALL unbinded apps are muted -> Unmute ALL unbinded apps
        """
        if not self.driver: return
        
        bound_apps = self._get_bound_apps()
        all_apps = self.driver.get_all_audio_apps()
        
        unbinded_apps = [app for app in all_apps if app not in bound_apps]
        
        if not unbinded_apps:
            return

        # Check if any unbinded app is currently unmuted
        any_unmuted = False
        for app_name in unbinded_apps:
            is_muted = self.driver.get_app_mute(app_name)
            if not is_muted:
                any_unmuted = True
                break
        
        # If any is unmuted, we want to mute all (target_mute = True)
        # If all are muted, we want to unmute all (target_mute = False)
        target_mute = any_unmuted
        
        for app_name in unbinded_apps:
            # We only need to toggle if the current state is different from target
            current_mute = self.driver.get_app_mute(app_name)
            if current_mute != target_mute:
                self.driver.toggle_app_mute(app_name)
    
    def set_unbinded_volumes(self, level):
        """Set volume for unbinded apps"""
        if not self.driver: return
        
        bound_apps = self._get_bound_apps()
        
        # Check for Current Application binding
        has_current_app_binding = False
        if self.config_manager:
            config = self.config_manager.load_config()
            for binding in config.get('variable_bindings', {}).values():
                targets = binding.get('app_name', []) if isinstance(binding, dict) else (binding if isinstance(binding, list) else [binding])
                if "Current Application" in targets or (isinstance(targets, list) and "Current Application" in targets):
                    has_current_app_binding = True
                    break
        
        focused_app = self.driver.get_focused_app() if has_current_app_binding else None
        
        all_apps = self.driver.get_all_audio_apps() if self.driver else {}
        
        # Set volume for apps that are not bound and not the focused app (if bound)
        for app_name in all_apps:
            if app_name not in bound_apps:
                if not focused_app or app_name != focused_app:
                    self.driver.set_app_volume(app_name, level)
        
    def get_all_audio_apps(self):
        """Get list of all active audio applications"""
        if self.driver:
            return self.driver.get_all_audio_apps()
        return {}
        
    def has_microphone(self):
        return self.driver.mic_volume is not None if self.driver else False

    def set_volume_tab(self, volume_tab):
        self.volume_tab = volume_tab

    def _get_bound_apps(self):
        """Get a set of all currently bound application names"""
        try:
            if not self.config_manager:
                return set()

            config = self.config_manager.load_config()
            bindings = config.get('variable_bindings', {})

            bound_apps = set()
            for binding in bindings.values():
                if isinstance(binding, dict):
                    app_names = binding.get('app_name', [])
                elif isinstance(binding, list):
                    app_names = binding
                else:
                    app_names = [binding] if binding else []

                if isinstance(app_names, str):
                    app_names = [app_names]

                for app_name in app_names:
                    if app_name not in ['Master', 'Microphone', 'System Sounds', 'Current Application', 'None', 'Unbinded']:
                        bound_apps.add(app_name)

            return bound_apps
        except Exception as e:
            log_error(e, "Error getting bound apps")
            return set()

    def cleanup(self):
        print("Cleaning up AudioManager...")
        if self.serial_controller:
            self.serial_controller.stop()
        if self.driver:
            self.driver.cleanup()