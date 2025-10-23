import subprocess
import time
from utils.error_handler import log_error


class ActionHandler:
    """Handle all button actions"""

    def __init__(self, audio_manager=None):
        self.audio_manager = audio_manager
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if required modules are available"""
        try:
            import keyboard
            self.has_keyboard = True
        except ImportError:
            self.has_keyboard = False
            log_error(
                ImportError("keyboard module not available"),
                "Install 'keyboard' for keybind actions"
            )

        try:
            import win32api
            import win32con
            self.has_win32 = True
        except ImportError:
            self.has_win32 = False

    def execute_action(self, action_type, **kwargs):
        """Execute a specific action"""
        try:
            action_map = {
                'play_pause': self.play_pause,
                'play': self.play,
                'pause': self.pause,
                'next_track': self.next_track,
                'previous_track': self.previous_track,
                'seek_forward': self.seek_forward,
                'seek_backward': self.seek_backward,
                'volume_up': self.volume_up,
                'volume_down': self.volume_down,
                'mute': self.mute,
                'switch_audio_output': self.switch_audio_output,
                'keybind': self.press_keybind,
                'launch_app': self.launch_app,
            }

            action = action_map.get(action_type)
            if action:
                return action(**kwargs)
            else:
                log_error(ValueError(f"Unknown action: {action_type}"), "Invalid action")
                return False

        except Exception as e:
            log_error(e, f"Error executing action: {action_type}")
            return False

    def play_pause(self):
        """Toggle play/pause"""
        try:
            self._send_media_key(0xB3)
   
        except Exception as e:
            log_error(e, "Error in play_pause")
            return False

    def play(self):
        """Play"""
        try:
            if self.has_keyboard:
                import keyboard
                keyboard.press_and_release('play media')
                return True
            else:
                self._send_media_key(0xB3)  # Play/Pause
                return True
        except Exception as e:
            log_error(e, "Error in play")
            return False

    def pause(self):
        """Pause"""
        try:
            if self.has_keyboard:
                import keyboard
                keyboard.press_and_release('pause media')
                return True
            else:
                self._send_media_key(0xB3)  # Play/Pause

        except Exception as e:
            log_error(e, "Error in pause")
            return False

    def next_track(self):
        """Next track"""
        try:
            self._send_media_key(0xB0)  # VK_MEDIA_NEXT_TRACK

        except Exception as e:
            log_error(e, "Error in next_track")
            return False

    def previous_track(self):
        """Previous track"""
        try:
            self._send_media_key(0xB1)  # VK_MEDIA_PREV_TRACK

        except Exception as e:
            log_error(e, "Error in previous_track")
            return False

    def seek_forward(self, seconds=5):
        """Seek forward (not all media players support this)"""
        try:
            if self.has_keyboard:
                import keyboard
                # Most players use Right arrow for seeking
                keyboard.press_and_release('right')
                return True
            else:
                return False
        except Exception as e:
            log_error(e, "Error in seek_forward")
            return False

    def seek_backward(self, seconds=5):
        """Seek backward (not all media players support this)"""
        try:
            if self.has_keyboard:
                import keyboard
                # Most players use Left arrow for seeking
                keyboard.press_and_release('left')
                return True
            else:
                return False
        except Exception as e:
            log_error(e, "Error in seek_backward")
            return False

    def volume_up(self):
        """Volume up"""
        try:
            self._send_media_key(0xAF)  # VK_VOLUME_UP

        except Exception as e:
            log_error(e, "Error in volume_up")
            return False

    def volume_down(self):
        """Volume down"""
        try:
            self._send_media_key(0xAE)  # VK_VOLUME_DOWN
            
        except Exception as e:
            log_error(e, "Error in volume_down")
            return False

    def mute(self, target=None):
        """Mute/unmute"""
        try:
            if target and self.audio_manager:
                # Mute specific target
                if target == "Master":
                    current = self.audio_manager.master_volume.GetMute()
                    self.audio_manager.master_volume.SetMute(not current, None)
                    return True
                elif target == "Microphone":
                    if self.audio_manager.has_microphone():
                        current = self.audio_manager.mic_volume.GetMute()
                        self.audio_manager.mic_volume.SetMute(not current, None)
                        return True
                else:
                    # Mute specific app
                    return self.audio_manager.toggle_app_mute(target)
            else:
                self._send_media_key(0xAD)  # VK_VOLUME_MUTE

        except Exception as e:
            log_error(e, "Error in mute")
            return False

    def switch_audio_output(self):
        """Switch audio output device"""
        try:
            # This requires AudioDeviceCmdlets or SoundSwitch
            # For now, we'll open the sound settings
            subprocess.Popen(['control', 'mmsys.cpl', 'sounds'])
            return True
        except Exception as e:
            log_error(e, "Error switching audio output")
            return False

    def press_keybind(self, keys):
        """Press a custom keybind"""
        try:
            if not self.has_keyboard:
                log_error(
                    ImportError("keyboard module not available"),
                    "Cannot execute keybind"
                )
                return False

            import keyboard

            if isinstance(keys, str):
                # Single key or combination like "ctrl+c"
                keyboard.press_and_release(keys)
                return True
            elif isinstance(keys, list):
                # Multiple keys in sequence
                for key in keys:
                    keyboard.press_and_release(key)
                    time.sleep(0.05)
                return True
            else:
                return False

        except Exception as e:
            log_error(e, f"Error pressing keybind: {keys}")
            return False

    def launch_app(self, app_path=None):
        """Launch an application by path or name"""
        try:
            if not app_path:
                log_error(ValueError("No app path provided"), "Cannot launch app")
                return False

            # Strip whitespace
            app_path = app_path.strip()
            
            if not app_path:
                log_error(ValueError("Empty app path provided"), "Cannot launch app")
                return False

            # Handle paths with quotes - remove them for proper subprocess handling
            # Supports: "C:\Program Files\App\app.exe" -> C:\Program Files\App\app.exe
            if app_path.startswith('"') and app_path.endswith('"'):
                app_path = app_path[1:-1]
            elif app_path.startswith("'") and app_path.endswith("'"):
                app_path = app_path[1:-1]

            # Try to launch the application
            # This supports both full paths (e.g., "C:\Program Files\App\app.exe")
            # and simple names (e.g., "notepad", "calc")
            subprocess.Popen(app_path, shell=False)
            return True

        except Exception as e:
            log_error(e, f"Error launching app: {app_path}")
            return False

    def _send_media_key(self, vk_code):
        """Send a media key using Windows API"""
        try:
            if self.has_win32:
                import win32api
                import win32con

                # Press
                win32api.keybd_event(vk_code, 0, 0, 0)
                time.sleep(0.05)
                # Release
                win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                return True
            else:
                return False
        except Exception as e:
            log_error(e, f"Error sending media key: {vk_code}")
            return False