from abc import ABC, abstractmethod

class AudioDriver(ABC):
    """Abstract base class for audio drivers"""

    @abstractmethod
    def initialize(self):
        """Initialize the audio driver"""
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup resources"""
        pass

    @abstractmethod
    def get_devices(self):
        """Get available audio devices"""
        pass
    
    @abstractmethod
    def get_default_device(self):
        """Get the default audio device"""
        pass

    @abstractmethod
    def set_master_volume(self, level):
        """Set master volume (0.0 to 1.0)"""
        pass

    @abstractmethod
    def set_mic_volume(self, level):
        """Set microphone volume (0.0 to 1.0)"""
        pass
    
    @abstractmethod
    def set_system_sounds_volume(self, level):
        """Set system sounds volume (0.0 to 1.0)"""
        pass

    @abstractmethod
    def set_app_volume(self, app_name, level):
        """Set volume for a specific application"""
        pass

    @abstractmethod
    def toggle_master_mute(self):
        """Toggle master mute"""
        pass

    @abstractmethod
    def toggle_mic_mute(self):
        """Toggle microphone mute"""
        pass

    @abstractmethod
    def toggle_app_mute(self, app_name):
        """Toggle mute for a specific application"""
        pass

    @abstractmethod
    def get_all_audio_apps(self):
        """Get list of all applications with audio sessions"""
        pass

    @abstractmethod
    def get_focused_app(self):
        """Get the name of the currently focused application"""
        pass
