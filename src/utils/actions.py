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

    def _run_powershell_hidden(self, command, timeout=10):
        """Run PowerShell command with hidden window - same as output_switch.py"""
        if platform.system() == "Windows":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE

            creation_flags = CREATE_NO_WINDOW
            if hasattr(subprocess, 'CREATE_NO_WINDOW'):
                creation_flags |= subprocess.CREATE_NO_WINDOW

            return subprocess.run(
                ["powershell.exe", "-WindowStyle", "Hidden", "-NoProfile",
                 "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                startupinfo=si,
                creationflags=creation_flags,
                shell=False
            )
        else:
            return subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout
            )

    def _check_audio_cmdlets(self):
        """Check if AudioDeviceCmdlets is installed on Windows"""
        if self._audio_cmdlets_checked:
            return self._audio_cmdlets_available

        if platform.system() != "Windows":
            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = True
            return True

        try:
            # Use simpler, faster command that won't timeout
            ps_command = "Get-Module -ListAvailable AudioDeviceCmdlets | Select-Object -First 1 -ExpandProperty Name"
            result = self._run_powershell_hidden(ps_command, timeout=8)

            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = (
                result.returncode == 0 and
                "AudioDeviceCmdlets" in result.stdout
            )
            return self._audio_cmdlets_available

        except subprocess.TimeoutExpired:
            log_error(
                TimeoutError("PowerShell command timed out"),
                "AudioDeviceCmdlets check timed out - assuming not installed"
            )
            self._audio_cmdlets_checked = True
            self._audio_cmdlets_available = False
            return False
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
                text="AudioDeviceCmdlets Not Found",
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

    # Mapping of Display Name -> Internal Action Type
    ACTION_MAP = {
        "Play/Pause": "play_pause",
        "Play": "play",
        "Pause": "pause",
        "Next": "next_track",
        "Previous": "previous_track",
        "Seek Forward": "seek_forward",
        "Seek Backward": "seek_backward",
        "Volume Up": "volume_up",
        "Volume Down": "volume_down",
        "Mute": "mute",
        "Switch Audio Output": "switch_audio_output",
        "Keybind": "keybind",
        "Launch app": "launch_app",
    }

    def execute_action(self, action_name, **kwargs):
        """Execute a specific action by name (display name or internal type)"""
        try:
            # Resolve action type from map if possible
            action_type = self.ACTION_MAP.get(action_name, action_name)
            
            # Legacy/Internal function mapping
            func_map = {
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

            action = func_map.get(action_type)
            if action:
                return action(**kwargs)
            else:
                log_error(ValueError(f"Unknown action: {action_name} (mapped to {action_type})"), "Invalid action")
                return False

        except Exception as e:
            log_error(e, f"Error executing action: {action_name}")
            return False

    def play_pause(self, **kwargs):
        """Toggle play/pause"""
        try:
            self._send_media_key(0xB3)
            return True
        except Exception as e:
            log_error(e, "Error in play_pause")
            return False

    def play(self, **kwargs):
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

    def pause(self, **kwargs):
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

    def next_track(self, **kwargs):
        """Next track"""
        try:
            self._send_media_key(0xB0)
            return True
        except Exception as e:
            log_error(e, "Error in next_track")
            return False

    def previous_track(self, **kwargs):
        """Previous track"""
        try:
            self._send_media_key(0xB1)
            return True
        except Exception as e:
            log_error(e, "Error in previous_track")
            return False

    def seek_forward(self, seconds=5, **kwargs):
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

    def seek_backward(self, seconds=5, **kwargs):
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

    def volume_up(self, **kwargs):
        """Volume up"""
        try:
            self._send_media_key(0xAF)
            return True
        except Exception as e:
            log_error(e, "Error in volume_up")
            return False

    def volume_down(self, **kwargs):
        """Volume down"""
        try:
            self._send_media_key(0xAE)
            return True
        except Exception as e:
            log_error(e, "Error in volume_down")
            return False

    def mute(self, **kwargs):
        """Toggle mute"""
        try:
            if not self.audio_manager:
                return False

            # Schema mapping:
            # value = "Mute"
            # argument = target (e.g. "Master", "Microphone", "Specific App Name")
            
            target = kwargs.get('argument') or kwargs.get('target')
            
            # Legacy/Fallback
            if not target:
                 target = 'Master'
            
            # Handle empty target as Master
            if not target or target == "None":
                target = "Master"

            if target == "Master":
                self.audio_manager.toggle_master_mute()
            elif target == "Microphone":
                self.audio_manager.toggle_mic_mute()
            elif target == "System Sounds":
                self.audio_manager.toggle_system_sounds_mute()
            elif target == "Current Application":
                self.audio_manager.toggle_current_app_mute()
            elif target == "Unbound":
                self.audio_manager.toggle_unbound_mute()
            else:
                # Specific app
                self.audio_manager.toggle_app_mute(target)
                
            return True
        except Exception as e:
            log_error(e, "Error in mute")
            return False

    def switch_audio_output(self, output_mode="cycle", device_name=None, **kwargs):
        """Switch audio output device"""
        try:
            # Check if AudioDeviceCmdlets is installed on Windows
            if not self._check_audio_cmdlets():
                self._show_audio_cmdlets_install_dialog()
                return False

            from audio.output_switch import (
                cycle_audio_device,
                set_audio_device,
                get_device_names
            )

            # Schema mappping:
            # value = "Switch Audio Output"
            # argument = "Cycle Through" OR Device Name (for select mode)
            
            arg = kwargs.get('argument')
            
            # Determine mode based on argument
            if arg == "Cycle Through" or arg is None:
                final_mode = "cycle"
                final_device = None
            else:
                final_mode = "select"
                final_device = arg

            # Allow direct overrides if provided via kwargs (legacy)
            if kwargs.get('output_mode'): final_mode = kwargs.get('output_mode')
            if device_name: final_device = device_name
            
            if final_mode == "cycle":
                return cycle_audio_device()

            elif final_mode == "select" and final_device:
                # Verify device exists by checking available names
                available_names = get_device_names()

                if not available_names:
                    log_error(ValueError("No audio devices found"), "Cannot switch audio output")
                    return False

                if final_device not in available_names:
                    log_error(ValueError(f"Device not found: {final_device}"), "Cannot switch audio output")
                    return False

                return set_audio_device(final_device)

            else:
                return False

        except Exception as e:
            log_error(e, "Error switching audio output")
            return False

    def press_keybind(self, keys, **kwargs):
        """Press a custom keybind"""
        try:
            if not self.has_keyboard:
                log_error(
                    ImportError("keyboard module not available"),
                    "Cannot execute keybind"
                )
                return False
            

            import keyboard
            
            # Support generic binding structure
            if not keys:
                keys = kwargs.get('value') or kwargs.get('argument')
                
            if not keys:
                return False
                
            keyboard.press_and_release(keys)
            return True

        except Exception as e:
            log_error(e, f"Error pressing keybind: {keys}")
            return False

    def launch_app(self, app_path=None, **kwargs):
        """Launch an application by path or name"""
        try:
            # Schema mapping:
            # value = "Launch app"
            # argument = Display Name (e.g. "Chrome")
            # argument2 = Exe Path / Command (e.g. "C:\Path\To\Chrome.exe" --arg)
            
            path_to_use = app_path
            
            if not path_to_use:
                # Priority: argument2 (path) > argument (fallback path)
                path_to_use = kwargs.get('argument2') or kwargs.get('argument')
                
            if not path_to_use:
                log_error(ValueError("No app path provided"), "Cannot launch app")
                return False

            path_to_use = path_to_use.strip()

            if not path_to_use:
                log_error(ValueError("Empty app path provided"), "Cannot launch app")
                return False
            
            # Note: subprocess.Popen with shell=True handles quotes reasonably well usually,
            # but we might want to clean just outer quotes if present.
            if path_to_use.startswith('"') and path_to_use.endswith('"'):
                path_to_use = path_to_use[1:-1]
            elif path_to_use.startswith("'") and path_to_use.endswith("'"):
                path_to_use = path_to_use[1:-1]

            subprocess.Popen(path_to_use, shell=True)
            return True

        except Exception as e:
            log_error(e, f"Error launching app: {app_path}")
            return False

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