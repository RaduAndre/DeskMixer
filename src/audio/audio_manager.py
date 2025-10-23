from utils.error_handler import log_error

# Try importing heavy audio libs; allow app to run without them (degraded mode).
AUDIO_AVAILABLE = True
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
except Exception as _e:
    AUDIO_AVAILABLE = False
    log_error(_e, "Audio libraries (comtypes/pycaw) not available - running in degraded mode")


class AudioManager:
    """Manages all audio-related operations"""

    def __init__(self):
        self.master_volume = None
        self.mic_volume = None
        self.app_sessions = {}
        self.serial_handler = None
        self.config_manager = None
        # window_monitor may be set externally if needed by bindings
        self.window_monitor = None
        self.system_sounds_session = None
        self.last_focused_app = None  # Track last focused app for debugging

        if AUDIO_AVAILABLE:
            self._initialize()
        else:
            # In degraded mode, keep attributes present but avoid calling heavy initialization.
            log_error(Exception("Audio libs missing"), "AudioManager initialized in degraded mode")

    def _initialize(self):
        """Initialize audio devices"""
        try:
            # Master volume
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.master_volume = cast(interface, POINTER(IAudioEndpointVolume))

            # Microphone
            try:
                mic_devices = AudioUtilities.GetMicrophone()
                mic_interface = mic_devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self.mic_volume = cast(mic_interface, POINTER(IAudioEndpointVolume))
            except Exception as e:
                log_error(e, "Microphone not available")
                self.mic_volume = None

        except Exception as e:
            log_error(e, "Failed to initialize audio devices")
            raise

    def _refresh_system_sounds_session(self):
        """Refresh and find the system sounds audio session"""
        try:
            if not AUDIO_AVAILABLE:
                return False
            
            sessions = AudioUtilities.GetAllSessions()
            
            for session in sessions:
                try:
                    # System sounds don't have a process, check DisplayName instead
                    if session.Process is None or session.Process.name() is None:
                        volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)
                        # This is likely the system sounds session
                        self.system_sounds_session = volume_interface
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            log_error(e, "Error refreshing system sounds session")
            return False

    def set_app_volume(self, app_name, level, mode='normal'):
        """Set volume for specific application with curve applied"""
        try:
            if not AUDIO_AVAILABLE:
                return False
            
            # Refresh sessions to make sure we have the latest
            if app_name not in self.app_sessions:
                self.get_all_audio_apps()
            
            if app_name in self.app_sessions:
                adjusted_level = self._apply_volume_curve(level, mode)
                self.app_sessions[app_name].SetMasterVolume(adjusted_level, None)
                return True
        except Exception as e:
            log_error(e, f"Error setting volume for {app_name}")

        return False

    def toggle_app_mute(self, app_name):
        """Toggle mute for specific application"""
        try:
            if not AUDIO_AVAILABLE:
                return False
            if app_name in self.app_sessions:
                session = self.app_sessions[app_name]
                current_mute = session.GetMute()
                session.SetMute(not current_mute, None)
                return True
        except Exception as e:
            log_error(e, f"Error toggling mute for {app_name}")

        return False

    def set_handlers(self, serial_handler, config_manager):
        """Set the serial and config handlers"""
        self.serial_handler = serial_handler
        self.config_manager = config_manager

        if self.serial_handler:
            self.serial_handler.add_callback(self._handle_serial_data)

    def set_volume_tab(self, volume_tab):
        """Set reference to volume tab for UI updates"""
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
                # Handle different binding formats
                if isinstance(binding, dict):
                    app_names = binding.get('app_name', [])
                elif isinstance(binding, list):
                    app_names = binding
                else:
                    app_names = [binding] if binding else []
                
                # Normalize to list
                if isinstance(app_names, str):
                    app_names = [app_names]
                
                # Add non-special bindings to the set
                for app_name in app_names:
                    if app_name not in ['Master', 'Microphone', 'System Sounds', 'Current Application', 'None', 'Unbinded']:
                        bound_apps.add(app_name)
            
            return bound_apps
            
        except Exception as e:
            log_error(e, "Error getting bound apps")
            return set()

    def _get_focused_app_process(self):
        """Get the process name of the currently focused window with improved detection"""
        try:
            if not AUDIO_AVAILABLE:
                return None
            
            # Import win32 libraries for getting process info
            try:
                import win32gui
                import win32process
                import psutil
            except ImportError as e:
                log_error(e, "win32gui/psutil not available - Cannot get process from window")
                return None
            
            # Get the foreground window handle
            hwnd = win32gui.GetForegroundWindow()
            
            if not hwnd:
                return None
            
            try:
                # Get window title for debugging
                window_title = win32gui.GetWindowText(hwnd)
            except Exception as e:
                log_error(e, "Could not get window title: {e}")
            
            try:
                # Get the process ID from the window handle
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                
                if not pid:
                    return None
                
                # Get the process using psutil
                process = psutil.Process(pid)
                process_name = process.name()
                
                # Also get the executable path for more options
                try:
                    exe_path = process.exe()
                except:
                    pass
                
                return process_name
                
            except psutil.NoSuchProcess:
                return None
            except psutil.AccessDenied:
                return None
            except Exception as e:
                return None
            
        except Exception as e:
            log_error(e, "Error getting focused app process")
            return None

    def _find_matching_audio_session(self, process_name):
        """Find matching audio session for a process name with fuzzy matching"""
        if not process_name:
            return None
        
        # Try exact match first
        if process_name in self.app_sessions:
            return process_name
        
        # Try with .exe extension
        if not process_name.lower().endswith('.exe'):
            with_exe = process_name + '.exe'
            if with_exe in self.app_sessions:
                return with_exe
        
        # Try without .exe extension
        if process_name.lower().endswith('.exe'):
            without_exe = process_name[:-4]
            if without_exe in self.app_sessions:
                return without_exe
        
        # Try case-insensitive match
        process_lower = process_name.lower()
        for session_name in self.app_sessions.keys():
            if session_name.lower() == process_lower:
                return session_name
        
        # Try case-insensitive match with .exe variants
        for session_name in self.app_sessions.keys():
            session_lower = session_name.lower()
            if session_lower == process_lower + '.exe' or session_lower + '.exe' == process_lower:
                return session_name
        
        return None

    def _handle_serial_data(self, data):
        """Handle incoming serial data"""
        try:
            if not data or not isinstance(data, str):
                return

            # Handle button presses
            if data.startswith('b'):
                parts = data.strip().split()
                if len(parts) == 2:
                    button_id, state = parts
                    self._handle_button_action(button_id, state)
                return

            # Handle slider data
            if '|' in data:
                sliders_data = {}
                parts = [p for p in data.strip().split('|') if p.strip()]
                
                for part in parts:
                    try:
                        values = part.strip().split()
                        if len(values) == 2:
                            key, value = values
                            if key.startswith('s'):
                                try:
                                    normalized_value = float(value) / 1023.0
                                    sliders_data[key] = normalized_value
                                except ValueError:
                                    continue
                    except Exception:
                        continue

            if sliders_data and self.config_manager:
                config = self.config_manager.load_config()
                bindings = config.get('variable_bindings', {})
                
                # Get global mode setting
                slider_sampling = self.config_manager.get_slider_sampling()
                
                for slider_id, value in sliders_data.items():
                    binding = bindings.get(slider_id)
                    if binding:
                        # Normalize to list format
                        if isinstance(binding, dict):
                            targets = binding.get('app_name', [])
                        elif isinstance(binding, list):
                            targets = binding
                        else:
                            targets = [binding] if binding else []
                        
                        if isinstance(targets, str):
                            targets = [targets]
                        
                        # Process each target
                        for target in targets:
                            if target == "Master":
                                self.set_master_volume(value, slider_sampling)
                            elif target == "Microphone":
                                self.set_mic_volume(value, slider_sampling)
                            elif target == "System Sounds":
                                self.set_system_sounds_volume(value, slider_sampling)
                            elif target == "Unbinded":
                                # Set volume for all unbound apps
                                self.set_unbinded_volumes(value, slider_sampling)
                            elif target == "Current Application":
                                # ALWAYS refresh audio sessions before trying
                                self.get_all_audio_apps()
                                
                                # Get the focused process name
                                process_name = self._get_focused_app_process()
                                
                                if process_name:
                                    self.last_focused_app = process_name
                                    
                                    # Find matching audio session
                                    matched_session = self._find_matching_audio_session(process_name)
                                    
                                    if matched_session:
                                        # Check if this app is already bound to another slider
                                        bound_apps = self._get_bound_apps()
                                        
                                        # Skip if already bound to a different slider
                                        if matched_session not in bound_apps:
                                            success = self.set_app_volume(matched_session, value, slider_sampling)
                                            
                                            if success:
                                                
                                                # Update volume tab if available
                                                if hasattr(self, 'volume_tab') and self.volume_tab:
                                                    try:
                                                        self.volume_tab.update_focused_app(matched_session)
                                                        self.volume_tab.update_volumes()
                                                    except Exception as e:
                                                        log_error(e, "Error updating volume tab")
                                
                            elif target == "None":
                                # Do nothing for None
                                pass
                            else:
                                # Specific application (custom or from list)
                                self.set_app_volume(target, value, slider_sampling)

        except Exception as e:
            log_error(e, f"Error handling serial data: {data}")

    def _handle_button_action(self, button_id, state):
        """Handle button press/release"""
        try:
            if not self.config_manager:
                return
                
            config = self.config_manager.load_config()
            binding = config.get('button_bindings', {}).get(button_id)
            
            if not binding:
                return
                
            # Only trigger on button press (state = 1)
            if state != '1':
                return
                
            action = binding.get('action')
            target = binding.get('target')
            keybind = binding.get('keybind')
            app_path = binding.get('app_path')  # ADD THIS LINE
            
            from utils.actions import ActionHandler
            action_handler = ActionHandler(self)
            
            kwargs = {}
            if target:
                kwargs['target'] = target
            if keybind:
                kwargs['keys'] = keybind
            if app_path:  # ADD THESE TWO LINES
                kwargs['app_path'] = app_path
                
            action_handler.execute_action(action, **kwargs)

        except Exception as e:
            log_error(e, f"Error handling button {button_id}")

    def _get_process_from_window(self, window_title):
        """Get the process executable name from the currently focused window (Legacy method - use _get_focused_app_process instead)"""
        return self._get_focused_app_process()

    def cleanup(self):
        """Cleanup audio resources"""
        try:
            self.app_sessions.clear()
            self.system_sounds_session = None
        except Exception as e:
            log_error(e, "Error during audio cleanup")

    def set_unbinded_volumes(self, level, mode='normal'):
        """Set volume for all unbinded applications with curve applied (excluding Master, Microphone, and currently focused app if Current Application binding exists)"""
        try:
            if not AUDIO_AVAILABLE:
                return

            # Get the set of bound apps BEFORE refreshing sessions
            bound_apps = self._get_bound_apps()
            
            # Check if any slider has "Current Application" binding
            has_current_app_binding = False
            if self.config_manager:
                config = self.config_manager.load_config()
                bindings = config.get('variable_bindings', {})
                
                for binding in bindings.values():
                    if isinstance(binding, dict):
                        targets = binding.get('app_name', [])
                    elif isinstance(binding, list):
                        targets = binding
                    else:
                        targets = [binding] if binding else []
                    
                    if isinstance(targets, str):
                        targets = [targets]
                    
                    if "Current Application" in targets:
                        has_current_app_binding = True
                        break
            
            # Get currently focused app to exclude if "Current Application" binding exists
            focused_session = None
            if has_current_app_binding:
                process_name = self._get_focused_app_process()
                if process_name:
                    # Get sessions first so we can match
                    self.get_all_audio_apps()
                    focused_session = self._find_matching_audio_session(process_name)
            else:
                # Still need to refresh sessions
                self.get_all_audio_apps()
            
            # Apply volume curve
            adjusted_level = self._apply_volume_curve(level, mode)
            
            # Create a snapshot of current sessions to avoid dictionary size change during iteration
            current_sessions = dict(self.app_sessions)
            
            # Set volume for all unbound apps
            for app_name, session in current_sessions.items():
                # Skip if app is bound to another slider
                if app_name in bound_apps:
                    continue
                
                # Skip if this is the focused app and "Current Application" binding exists (Current Application takes priority)
                if focused_session and app_name == focused_session:
                    continue
                
                try:
                    # Verify session still exists before trying to set volume
                    if app_name in self.app_sessions:
                        session.SetMasterVolume(adjusted_level, None)
                except Exception as e:
                    log_error(e, f"Error setting volume for {app_name}")

        except Exception as e:
            log_error(e, "Error setting unbinded volumes")

    def set_system_sounds_volume(self, level, mode='normal'):
        """Set volume for System Sounds (Windows notification sounds)"""
        try:
            if not AUDIO_AVAILABLE:
                return False
            
            adjusted_level = self._apply_volume_curve(level, mode)
            
            # Try to use cached session first
            if self.system_sounds_session:
                try:
                    self.system_sounds_session.SetMasterVolume(adjusted_level, None)
                    return True
                except:
                    # Session may have become invalid, refresh
                    self.system_sounds_session = None
            
            # Refresh and try again
            if self._refresh_system_sounds_session():
                try:
                    self.system_sounds_session.SetMasterVolume(adjusted_level, None)
                    return True
                except Exception as e:
                    log_error(e, "Error setting system sounds volume after refresh")
            
            # Alternative: Try to find in app_sessions (some systems show it there)
            self.get_all_audio_apps()
            for app_name in ["AudioSrv.Dll", "System Sounds", "svchost.exe"]:
                if app_name in self.app_sessions:
                    try:
                        self.app_sessions[app_name].SetMasterVolume(adjusted_level, None)
                        return True
                    except Exception as e:
                        log_error(e, f"Error setting volume for {app_name}")
            
            return False
            
        except Exception as e:
            log_error(e, "Error setting system sounds volume")
            return False

    def _apply_volume_curve(self, value, mode):
        """Apply volume curve based on mode setting"""
        try:
            if mode == "soft":
                # Soft curve: gentler at low volumes, more responsive at high
                return value ** 0.5
            elif mode == "hard":
                # Hard curve: less responsive at low volumes, more precise at high
                return value ** 2
            else:  # normal
                # Linear curve
                return value
        except Exception as e:
            log_error(e, f"Error applying volume curve for mode {mode}")
            return value

    def get_master_volume(self):
        """Get master volume level (0.0 to 1.0)"""
        try:
            if not AUDIO_AVAILABLE or not self.master_volume:
                return 0.5
            return self.master_volume.GetMasterVolumeLevelScalar()
        except Exception as e:
            log_error(e, "Error getting master volume")
            return 0.5

    def set_master_volume(self, level, mode='normal'):
        """Set master volume level (0.0 to 1.0) with curve applied"""
        try:
            if not AUDIO_AVAILABLE or not self.master_volume:
                return
            adjusted_level = self._apply_volume_curve(level, mode)
            self.master_volume.SetMasterVolumeLevelScalar(adjusted_level, None)
        except Exception as e:
            log_error(e, "Error setting master volume")

    def has_microphone(self):
        """Check if microphone is available"""
        return AUDIO_AVAILABLE and (self.mic_volume is not None)

    def get_mic_volume(self):
        """Get microphone volume level (0.0 to 1.0)"""
        try:
            if not AUDIO_AVAILABLE or not self.mic_volume:
                return 0.5
            return self.mic_volume.GetMasterVolumeLevelScalar()
        except Exception as e:
            log_error(e, "Error getting mic volume")
            return 0.5

    def set_mic_volume(self, level, mode='normal'):
        """Set microphone volume level (0.0 to 1.0) with curve applied"""
        try:
            if not AUDIO_AVAILABLE or not self.mic_volume:
                return
            adjusted_level = self._apply_volume_curve(level, mode)
            self.mic_volume.SetMasterVolumeLevelScalar(adjusted_level, None)
        except Exception as e:
            log_error(e, "Error setting mic volume")

    def get_all_audio_apps(self):
        """Get all applications with audio sessions"""
        apps = {}
        self.app_sessions.clear()

        if not AUDIO_AVAILABLE:
            return apps

        try:
            sessions = AudioUtilities.GetAllSessions()

            for session in sessions:
                if session.Process and session.Process.name():
                    try:
                        process_name = session.Process.name()
                        volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)

                        if process_name not in self.app_sessions:
                            self.app_sessions[process_name] = volume_interface
                            volume = volume_interface.GetMasterVolume()
                            apps[process_name] = volume

                    except Exception as e:
                        log_error(e, f"Error processing session for {session.Process.name()}")
                        continue

        except Exception as e:
            log_error(e, "Error getting audio applications")

        return apps

    def get_app_volume(self, app_name):
        """Get volume for specific application"""
        try:
            if not AUDIO_AVAILABLE:
                return None

            if app_name not in self.app_sessions:
                self.get_all_audio_apps()

            if app_name in self.app_sessions:
                return self.app_sessions[app_name].GetMasterVolume()

        except Exception as e:
            log_error(e, f"Error getting volume for {app_name}")
            
        return None