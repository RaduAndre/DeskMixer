import time
import threading
from ctypes import cast, POINTER
from comtypes import CoUninitialize, CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume, IAudioEndpointVolume

from audio.audio_driver import AudioDriver
from utils.error_handler import log_error

class WindowsAudioDriver(AudioDriver):
    """Windows implementation of AudioDriver using pycaw"""

    def __init__(self):
        self.master_volume = None
        self.mic_volume = None
        self.app_sessions = {}  # Stores lists of volume interfaces
        self.system_sounds_sessions = []
        self.current_device_id = None
        self._com_initialized = False
        self.monitor_running = False
        self.device_monitor_thread = None
        self.last_set_volumes = {}
        self.VOLUME_TOLERANCE = 0.005
        
        # Session caching to reduce CPU usage
        self.session_cache_timeout = 2.0  # seconds
        self.last_session_refresh_time = 0.0

    def initialize(self):
        """Initialize audio devices with error handling"""
        def init_operation():
            # Master volume
            speakers = AudioUtilities.GetSpeakers()
            self.master_volume = speakers.EndpointVolume
            
            try:
                self.current_device_id = speakers.id
            except Exception as e:
                log_error(e, "Could not get device ID")
                self.current_device_id = None

            # Microphone
            try:
                mic_device = AudioUtilities.GetMicrophone()
                if mic_device:
                    mic_interface = mic_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self.mic_volume = cast(mic_interface, POINTER(IAudioEndpointVolume))
                else:
                    self.mic_volume = None
            except Exception as e:
                log_error(e, "Microphone not available")
                self.mic_volume = None

            self._com_initialized = True
            return True

        success = self._safe_com_operation(
            init_operation,
            "audio device initialization",
            default_return=False
        )

        if not success:
            log_error(Exception("Initialization failed"), "Failed to initialize audio devices")
            raise RuntimeError("Audio device initialization failed")
            
        self._start_device_monitor()

    def _safe_com_operation(self, operation, operation_name="COM operation", default_return=None, retry_on_failure=True):
        try:
            return operation()
        except Exception as e:
            error_msg = f"COM error in {operation_name}: {str(e)}"
            com_errors_to_handle = [
                "access denied", "invalid pointer", "device not available",
                "no audio endpoint", "interface not found", "disconnected",
                "rpc server unavailable", "server execution failed"
            ]
            is_com_error = any(error in str(e).lower() for error in com_errors_to_handle)

            if is_com_error and retry_on_failure:
                log_error(e, f"{operation_name} failed with COM error, attempting recovery...")
                try:
                    if self.refresh_audio_devices():
                        time.sleep(0.1)
                        return operation()
                    else:
                        log_error(e, f"Recovery failed for {operation_name}")
                except Exception as recovery_error:
                    log_error(recovery_error, f"Recovery attempt failed for {operation_name}")

            log_error(e, error_msg)
            return default_return

    def _start_device_monitor(self):
        self.monitor_running = True
        self.device_monitor_thread = threading.Thread(target=self._monitor_device_changes, daemon=True)
        self.device_monitor_thread.start()

    def set_device_change_callback(self, callback):
        """Set callback to be called when audio device changes"""
        self.device_change_callback = callback

    def _monitor_device_changes(self):
        try:
            from comtypes import CoInitialize
            CoInitialize()
        except Exception as e:
            log_error(e, "Failed to initialize COM in monitor thread")

        while self.monitor_running:
            try:
                time.sleep(3.0)  # Device changes are rare, check every 3s
                def check_device_operation():
                    devices = AudioUtilities.GetSpeakers()
                    return devices.id

                new_device_id = self._safe_com_operation(
                    check_device_operation,
                    "device change detection",
                    default_return=self.current_device_id
                )

                if self.current_device_id and new_device_id != self.current_device_id:
                    print(f"Audio device changed! Refreshing... (Old: {self.current_device_id[:20]}..., New: {new_device_id[:20]}...)")
                    self.current_device_id = new_device_id
                    time.sleep(0.5)
                    self.refresh_audio_devices()
                    
                    # Notify callback if set
                    if hasattr(self, 'device_change_callback') and self.device_change_callback:
                        try:
                            self.device_change_callback()
                        except Exception as cb_err:
                            log_error(cb_err, "Error in device change callback")

            except Exception as e:
                if not hasattr(self, '_monitor_error_logged'):
                    log_error(e, "Error in device monitor thread")
                    self._monitor_error_logged = True
                time.sleep(5.0)

    def refresh_audio_devices(self):
        print("Refreshing audio devices...")
        def refresh_operation():
            speakers = AudioUtilities.GetSpeakers()
            self.master_volume = speakers.EndpointVolume
            try:
                self.current_device_id = speakers.id
            except Exception as e:
                log_error(e, "Could not get device ID during refresh")
                self.current_device_id = None

            try:
                mic_device = AudioUtilities.GetMicrophone()
                if mic_device:
                    mic_interface = mic_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    self.mic_volume = cast(mic_interface, POINTER(IAudioEndpointVolume))
                else:
                    self.mic_volume = None
            except Exception as e:
                log_error(e, "Microphone not available during refresh")
                self.mic_volume = None

            self.app_sessions.clear()
            self.get_all_audio_apps()
            self._refresh_system_sounds_session()
            print("Audio devices refreshed successfully!")
            return True

        return self._safe_com_operation(
            refresh_operation,
            "audio device refresh",
            default_return=False,
            retry_on_failure=False
        )

    def _refresh_system_sounds_session(self):
        def refresh_system_sounds_operation():
            sessions = AudioUtilities.GetAllSessions()
            self.system_sounds_sessions = []
            
            # Helper to check if session is already added
            def is_new(s):
                # Simple check, could be more robust with ID comparison if available
                return True 

            # Collect ALL candidates
            for session in sessions:
                is_match = False
                try:
                    # Strategy 1: Display Name
                    if session.DisplayName and "System Sounds" in session.DisplayName:
                        is_match = True
                    # Strategy 2: Known Process
                    elif session.Process and session.Process.name():
                        name = session.Process.name().lower()
                        if any(proc in name for proc in ["audiosrv", "sndvol.exe", "shellexperiencehost.exe"]):
                            is_match = True
                    # Strategy 3: No Process
                    elif session.Process is None:
                        is_match = True
                    
                    if is_match:
                        try:
                            valid_session = session._ctl.QueryInterface(ISimpleAudioVolume)
                            self.system_sounds_sessions.append(valid_session)
                        except: pass
                except: continue

            return len(self.system_sounds_sessions) > 0

        return self._safe_com_operation(
            refresh_system_sounds_operation,
            "system sounds session refresh",
            default_return=False
        )

    def get_devices(self):
        # For now, just return default device info or implement full enumeration if needed
        return [{"id": self.current_device_id, "name": "Default Device"}]

    def get_default_device(self):
        return {"id": self.current_device_id, "name": "Default Device"}

    def set_master_volume(self, level):
        if not self.master_volume:
            return

        # Clamp near-zero values to exactly 0 to prevent Windows API rounding
        if level < 0.01:
            level = 0.0

        last_level = self.last_set_volumes.get("Master", -1)
        if abs(level - last_level) < self.VOLUME_TOLERANCE:
            return

        self.last_set_volumes["Master"] = level

        def set_volume_operation():
            self.master_volume.SetMasterVolumeLevelScalar(level, None)
            return True

        success = self._safe_com_operation(
            set_volume_operation,
            "set master volume",
            default_return=False
        )
        
        if not success:
            self.refresh_audio_devices()
            self._safe_com_operation(
                set_volume_operation,
                "set master volume after refresh",
                default_return=False
            )

    def set_mic_volume(self, level):
        if not self.mic_volume:
            return

        # Clamp near-zero values to exactly 0 to prevent Windows API rounding
        if level < 0.01:
            level = 0.0

        last_level = self.last_set_volumes.get("Microphone", -1)
        if abs(level - last_level) < self.VOLUME_TOLERANCE:
            return

        self.last_set_volumes["Microphone"] = level

        def set_volume_operation():
            self.mic_volume.SetMasterVolumeLevelScalar(level, None)
            return True

        self._safe_com_operation(
            set_volume_operation,
            "set mic volume",
            default_return=False
        )

    def set_system_sounds_volume(self, level):
        # Clamp near-zero values to exactly 0 to prevent Windows API rounding
        if level < 0.01:
            level = 0.0

        last_level = self.last_set_volumes.get("System Sounds", -1)
        if abs(level - last_level) < self.VOLUME_TOLERANCE:
            return True

        self.last_set_volumes["System Sounds"] = level

        def set_system_volume_operation():
            success_count = 0
            
            if self.system_sounds_sessions:
                # Try setting on existing sessions
                active_sessions = []
                for session in self.system_sounds_sessions:
                    try:
                        session.SetMasterVolume(level, None)
                        active_sessions.append(session)
                        success_count += 1
                    except:
                        pass # stale session
                self.system_sounds_sessions = active_sessions

            # If no success or empty, refresh and try again
            if success_count == 0:
                if self._refresh_system_sounds_session():
                    for session in self.system_sounds_sessions:
                        try:
                            session.SetMasterVolume(level, None)
                            success_count += 1
                        except Exception as e:
                            log_error(e, "Error setting system sounds volume after refresh")

            return success_count > 0

        return self._safe_com_operation(
            set_system_volume_operation,
            "set system sounds volume",
            default_return=False
        )

    def set_app_volume(self, app_name, level):
        # Clamp near-zero values to exactly 0 to prevent Windows API rounding
        if level < 0.01:
            level = 0.0

        # Try using cached sessions first
        if app_name not in self.app_sessions:
            # Only refresh if cache is stale
            current_time = time.time()
            if current_time - self.last_session_refresh_time >= self.session_cache_timeout:
                self.get_all_audio_apps()
            
        # Case-insensitive lookup
        target_key = None
        if app_name in self.app_sessions:
            target_key = app_name
        else:
            # Try finding a case-insensitive match
            lower_name = app_name.lower()
            for key in self.app_sessions:
                if key.lower() == lower_name:
                    target_key = key
                    break
        
        if target_key:
            last_level = self.last_set_volumes.get(target_key, -1)
            if abs(level - last_level) < self.VOLUME_TOLERANCE:
                return True

            self.last_set_volumes[target_key] = level
            sessions = self.app_sessions[target_key]
            success_count = 0

            for session in sessions:
                def set_volume_operation(session_obj=session):
                    session_obj.SetMasterVolume(level, None)
                    return True

                success = self._safe_com_operation(
                    lambda: set_volume_operation(),
                    f"set volume for {target_key}",
                    default_return=False
                )
                if success:
                    success_count += 1
            
            return success_count > 0
        return False

    def toggle_master_mute(self):
        if not self.master_volume: return False
        try:
            current = self.master_volume.GetMute()
            self.master_volume.SetMute(not current, None)
            return True
        except Exception as e:
            log_error(e, "Error toggling master mute")
            return False

    def toggle_mic_mute(self):
        if not self.mic_volume: return False
        try:
            current = self.mic_volume.GetMute()
            self.mic_volume.SetMute(not current, None)
            return True
        except Exception as e:
            log_error(e, "Error toggling mic mute")
            return False

    def toggle_app_mute(self, app_name):
        # Case-insensitive lookup
        target_key = None
        if app_name in self.app_sessions:
            target_key = app_name
        else:
            lower_name = app_name.lower()
            for key in self.app_sessions:
                if key.lower() == lower_name:
                    target_key = key
                    break
        
        if target_key:
            sessions = self.app_sessions[target_key]
            if len(sessions) > 0:
                def get_mute_operation():
                    return sessions[0].GetMute()
                
                try:
                    current_mute = self._safe_com_operation(get_mute_operation, f"get mute {target_key}", default_return=False)
                except:
                    # Session may be stale, let cache handle refresh on next call
                    if target_key not in self.app_sessions: return False
                    sessions = self.app_sessions[target_key]
                    current_mute = self._safe_com_operation(get_mute_operation, f"get mute {target_key}", default_return=False)

                new_mute = not current_mute
                success_count = 0
                for session in sessions:
                    def set_mute_operation(session_obj=session):
                        session_obj.SetMute(new_mute, None)
                        return True
                    
                    if self._safe_com_operation(lambda: set_mute_operation(), f"set mute {target_key}", default_return=False):
                        success_count += 1
                
                return success_count > 0
        return False

    def get_app_mute(self, app_name):
        """Get mute state for a specific application"""
        # Case-insensitive lookup
        target_key = None
        if app_name in self.app_sessions:
            target_key = app_name
        else:
            lower_name = app_name.lower()
            for key in self.app_sessions:
                if key.lower() == lower_name:
                    target_key = key
                    break
                    
        if target_key:
            sessions = self.app_sessions[target_key]
            if len(sessions) > 0:
                def get_mute_operation():
                    return sessions[0].GetMute()
                
                return self._safe_com_operation(get_mute_operation, f"get mute {target_key}", default_return=False)
        return False

    def toggle_system_sounds_mute(self):
        """Toggle mute for system sounds"""
        def toggle_sys_mute_operation():
            success_count = 0
            
            # Refresh to be sure we have latest state
            self._refresh_system_sounds_session()
            
            if self.system_sounds_sessions:
                try:
                    # Get state from first valid one
                    current = self.system_sounds_sessions[0].GetMute()
                    new_mute = not current
                    
                    for session in self.system_sounds_sessions:
                        try:
                            session.SetMute(new_mute, None)
                            success_count += 1
                        except: pass
                    
                    if success_count > 0:
                         return True
                except: pass
             
            return False

        return self._safe_com_operation(
            toggle_sys_mute_operation, 
            "toggle system sounds mute", 
            default_return=False
        )

    def get_all_audio_apps(self):
        """Get all audio apps with caching to reduce CPU usage"""
        current_time = time.time()
        
        # Return cached data if recent enough
        if (self.app_sessions and 
            current_time - self.last_session_refresh_time < self.session_cache_timeout):
            # Return cached volume data without re-enumerating
            apps = {}
            for app_name, sessions in self.app_sessions.items():
                if len(sessions) > 0:
                    try:
                        volume = sessions[0].GetMasterVolume()
                        apps[app_name] = volume
                    except:
                        pass  # Session became invalid, will refresh next time
            return apps
        
        # Cache is stale, refresh sessions
        apps = {}
        self.app_sessions.clear()
        
        def get_sessions_operation():
            sessions = AudioUtilities.GetAllSessions()
            for session in sessions:
                if session.Process and session.Process.name():
                    try:
                        process_name = session.Process.name()
                        volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                        
                        if process_name not in self.app_sessions:
                            self.app_sessions[process_name] = []
                        self.app_sessions[process_name].append(volume_interface)
                        
                        volume = volume_interface.GetMasterVolume()
                        if process_name in apps:
                            apps[process_name] = (apps[process_name] + volume) / 2
                        else:
                            apps[process_name] = volume
                    except Exception as e:
                        log_error(e, f"Error processing session for {session.Process.name()}")
                        continue
            return apps

        result = self._safe_com_operation(
            get_sessions_operation,
            "get all audio apps",
            default_return={}
        )
        
        # Update cache timestamp after successful refresh
        self.last_session_refresh_time = current_time
        
        return result

    def get_focused_app(self):
        try:
            import win32gui
            import win32process
            import psutil
            
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd: return None
            
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid: return None
            
            process = psutil.Process(pid)
            return process.name()
        except Exception as e:
            log_error(e, "Error getting focused app")
            return None

    def cleanup(self):
        print("Cleaning up WindowsAudioDriver...")
        self.monitor_running = False
        if self.device_monitor_thread and self.device_monitor_thread.is_alive():
            self.device_monitor_thread.join(timeout=2.0)
        
        self.app_sessions.clear()
        self.system_sounds_sessions = []
        self.master_volume = None
        self.mic_volume = None
        
        if self._com_initialized:
            try:
                CoUninitialize()
                self._com_initialized = False
            except Exception as e:
                log_error(e, "Error during COM uninitialization")
