import os
import sys
from config.config_manager import ConfigManager
from utils.error_handler import log_error
from audio.audio_manager import AudioManager
from serial_comm.serial_handler import SerialHandler
from utils.system_startup import set_startup, check_startup_status

class CoreController:
    """
    Central controller for the application core logic.
    Decouples business logic from the UI.
    """
    def __init__(self):
        self.config_manager = ConfigManager()
        self.audio_manager = AudioManager()
        self.serial_handler = SerialHandler(self.config_manager)
        
        # Connect components
        self.audio_manager.set_handlers(self.serial_handler, self.config_manager)
        
        # Initialize state
        self.is_running = True
        
    def start(self):
        """Start core services"""
        try:
            # Serial handler is started by AudioManager -> SerialController
            # But we can ensure everything is ready here
            # Start connection process
            if self.serial_handler:
                import threading
                connection_thread = threading.Thread(target=self.serial_handler.auto_connect, daemon=True)
                connection_thread.start()
        except Exception as e:
            log_error(e, "Error starting CoreController")

    def stop(self):
        """Stop core services"""
        self.is_running = False
        if self.audio_manager:
            self.audio_manager.cleanup()
            
    def get_start_in_tray(self):
        """Get start in tray preference"""
        return self.config_manager.get_start_in_tray(default=False)
        
    def set_start_in_tray(self, value):
        """Set start in tray preference"""
        # This requires updating the config
        # For now, we'll assume the UI handles the config update via ConfigManager directly
        # or we can add a method to ConfigManager to update specific keys
        pass

    def is_start_on_boot_enabled(self):
        """Check if start on boot is enabled"""
        return check_startup_status()
        
    def set_start_on_boot(self, enabled):
        """Set start on boot preference"""
        return set_startup(enabled)
