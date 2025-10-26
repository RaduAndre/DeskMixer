import subprocess
import time
import platform
from utils.error_handler import log_error

# Windows-specific: Hide console windows
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    CREATE_NO_WINDOW = 0x08000000
else:
    startupinfo = None
    CREATE_NO_WINDOW = 0


class ActionHandler:
    """Handle all button actions"""

    def __init__(self, audio_manager=None):
        self.audio_manager = audio_manager
        self._check_dependencies()
        self._audio_cmdlets_checked = False
        self._audio_cmdlets_available = False

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

    def _check_audio_cmdlets(self):
        """Check if AudioDeviceCmdlets is installed on Windows"""
        if self._audio_cmdlets_checked:
            return self._audio_cmdlets_available

        if platform.system() != "Windows":
            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = True
            return True

        try:
            ps_command = "Get-Module -ListAvailable -Name AudioDeviceCmdlets"
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5
            )

            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = result.returncode == 0 and result.stdout.strip() != ""
            return self._audio_cmdlets_available

        except Exception as e:
            log_error(e, "Error checking AudioDeviceCmdlets")
            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = False
            return False

    def _show_audio_cmdlets_install_dialog(self):
        """Show installation instructions for AudioDeviceCmdlets"""
        try:
            import tkinter as tk
            from tkinter import messagebox

            message = """AudioDeviceCmdlets PowerShell module is not installed.

This module is required for audio output switching on Windows.

Installation Instructions:

1. Open PowerShell as Administrator
   (Right-click Start → Windows PowerShell (Admin))

2. Run this command:
   Install-Module -Name AudioDeviceCmdlets -Force

3. If prompted about repository trust, type 'Y' and press Enter

4. Wait for installation to complete

5. Restart this application

Alternative: You can also install manually from:
https://github.com/frgnca/AudioDeviceCmdlets"""

            # Create a custom dialog
            dialog = tk.Toplevel()
            dialog.title("AudioDeviceCmdlets Required")
            dialog.geometry("600x400")
            dialog.configure(bg="#2d2d2d")
            dialog.transient()
            dialog.grab_set()

            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (600 // 2)
            y = (dialog.winfo_screenheight() // 2) - (400 // 2)
            dialog.geometry(f"600x400+{x}+{y}")

            # Title
            title_label = tk.Label(
                dialog,
                text="⚠️ AudioDeviceCmdlets Not Found",
                bg="#2d2d2d",
                fg="#ffaa00",
                font=("Arial", 14, "bold"),
                pady=10
            )
            title_label.pack()

            # Message
            text_widget = tk.Text(
                dialog,
                bg="#1e1e1e",
                fg="white",
                font=("Consolas", 10),
                wrap="word",
                padx=15,
                pady=15,
                relief="flat"
            )
            text_widget.pack(fill="both", expand=True, padx=20, pady=10)
            text_widget.insert("1.0", message)
            text_widget.configure(state="disabled")

            # Command to copy
            command_frame = tk.Frame(dialog, bg="#2d2d2d")
            command_frame.pack(fill="x", padx=20, pady=5)

            tk.Label(
                command_frame,
                text="Command to copy:",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 9)
            ).pack(anchor="w")

            command_entry = tk.Entry(
                command_frame,
                bg="#1e1e1e",
                fg="white",
                font=("Consolas", 10),
                relief="flat"
            )
            command_entry.pack(fill="x", pady=5)
            command_entry.insert(0, "Install-Module -Name AudioDeviceCmdlets -Force")
            command_entry.configure(state="readonly")

            def copy_command():
                dialog.clipboard_clear()
                dialog.clipboard_append("Install-Module -Name AudioDeviceCmdlets -Force")
                copy_btn.configure(text="✓ Copied!")
                dialog.after(2000, lambda: copy_btn.configure(text="📋 Copy Command"))

            # Buttons
            button_frame = tk.Frame(dialog, bg="#2d2d2d")
            button_frame.pack(pady=10)

            copy_btn = tk.Button(
                button_frame,
                text="📋 Copy Command",
                command=copy_command,
                bg="#404040",
                fg="white",
                font=("Arial", 10, "bold"),
                relief="flat",
                padx=15,
                pady=8,
                cursor="hand2"
            )
            copy_btn.pack(side="left", padx=5)

            close_btn = tk.Button(
                button_frame,
                text="Close",
                command=dialog.destroy,
                bg="#404040",
                fg="white",
                font=("Arial", 10),
                relief="flat",
                padx=20,
                pady=8,
                cursor="hand2"
            )
            close_btn.pack(side="left", padx=5)

            dialog.wait_window()

        except Exception as e:
            log_error(e, "Error showing AudioDeviceCmdlets dialog")
            # Fallback to simple messagebox
            try:
                from tkinter import messagebox
                messagebox.showwarning(
                    "AudioDeviceCmdlets Required",
                    "AudioDeviceCmdlets PowerShell module is not installed.\n\n"
                    "To install:\n"
                    "1. Open PowerShell as Administrator\n"
                    "2. Run: Install-Module -Name AudioDeviceCmdlets -Force\n"
                    "3. Restart this application"
                )
            except:
                pass

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
            return True
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
                self._send_media_key(0xB3)
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
                self._send_media_key(0xB3)
                return True
        except Exception as e:
            log_error(e, "Error in pause")
            return False

    def next_track(self):
        """Next track"""
        try:
            self._send_media_key(0xB0)
            return True
        except Exception as e:
            log_error(e, "Error in next_track")
            return False

    def previous_track(self):
        """Previous track"""
        try:
            self._send_media_key(0xB1)
            return True
        except Exception as e:
            log_error(e, "Error in previous_track")
            return False

    def seek_forward(self, seconds=5):
        """Seek forward (not all media players support this)"""
        try:
            if self.has_keyboard:
                import keyboard
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
            self._send_media_key(0xAF)
            return True
        except Exception as e:
            log_error(e, "Error in volume_up")
            return False

    def volume_down(self):
        """Volume down"""
        try:
            self._send_media_key(0xAE)
            return True
        except Exception as e:
            log_error(e, "Error in volume_down")
            return False

    def mute(self, target=None):
        """Mute/unmute"""
        try:
            if target and self.audio_manager:
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
                    return self.audio_manager.toggle_app_mute(target)
            else:
                self._send_media_key(0xAD)
                return True
        except Exception as e:
            log_error(e, "Error in mute")
            return False

    def switch_audio_output(self, output_mode="cycle", device_name=None):
        """Switch audio output device

        Args:
            output_mode: "cycle" to cycle through devices, "select" to choose specific device
            device_name: Name of device to select (only used when output_mode="select")
        """
        try:
            # Check if AudioDeviceCmdlets is installed on Windows
            if not self._check_audio_cmdlets():
                self._show_audio_cmdlets_install_dialog()
                return False

            from utils.output_switch import (
                cycle_audio_device,
                set_audio_device,
                get_audio_devices
            )

            if output_mode == "cycle":
                return cycle_audio_device()
            elif output_mode == "select" and device_name:
                devices = get_audio_devices()
                if not devices:
                    log_error(ValueError("No audio devices found"), "Cannot switch audio output")
                    return False

                # Find device by name
                system = platform.system()

                for device in devices:
                    device_display_name = device.get('Name' if system == "Windows" else 'name', '')
                    if device_display_name == device_name:
                        return set_audio_device(device)

                log_error(ValueError(f"Device not found: {device_name}"), "Cannot switch audio output")
                return False
            else:
                return False

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
                keyboard.press_and_release(keys)
                return True
            elif isinstance(keys, list):
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

            app_path = app_path.strip()

            if not app_path:
                log_error(ValueError("Empty app path provided"), "Cannot launch app")
                return False

            if app_path.startswith('"') and app_path.endswith('"'):
                app_path = app_path[1:-1]
            elif app_path.startswith("'") and app_path.endswith("'"):
                app_path = app_path[1:-1]

            subprocess.Popen(app_path, shell=True)
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

                win32api.keybd_event(vk_code, 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                return True
            else:
                return False
        except Exception as e:
            log_error(e, f"Error sending media key: {vk_code}")
            return False